from typing import Optional, Any, Dict, List
from app.models.schemas import DownloadRequest
from fastapi import APIRouter, HTTPException
from app.db import table, enriched_table
from boto3.dynamodb.conditions import Key, Attr
import traceback
from decimal import Decimal

from fastapi.responses import Response
import csv
import io
import boto3, os

router = APIRouter()
GSI_NAME = "project-time-index"
s3_client = boto3.client("s3")
AWS_S3_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME")


@router.get("/detections")
def get_detections(
    projectName: Optional[str] = None,
    startTime: Optional[int] = None,
    endTime: Optional[int] = None,
):
    filter_conditions = []
    if projectName:
        filter_conditions.append(Attr("projectName").contains(projectName))
    if startTime and endTime:
        filter_conditions.append(Attr("create_time").between(startTime, endTime))
    elif startTime:
        filter_conditions.append(Attr("create_time").gte(startTime))
    elif endTime:
        filter_conditions.append(Attr("create_time").lte(endTime))
    try:
        scan_args = {}
        if filter_conditions:
            final_filter = None
            if filter_conditions:
                from functools import reduce

                final_filter = reduce(lambda a, b: a & b, filter_conditions)

            if final_filter:
                scan_args["FilterExpression"] = final_filter
        response = table.scan(**scan_args)

        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("create_time", 0), reverse=True)

        return {
            "code": 200,
            "message": f"Successfully retrieved {len(items)} analysis sessions (via Scan).",
            "data": items,
        }
    except Exception as e:
        print(f"Error scanning DynamoDB: {e}")
        raise HTTPException(status_code=500, detail="Failed to query database.")


@router.get("/download")
def download_csv(session_id: str):
    try:
        response = table.get_item(Key={"session_id": session_id})
        item = response.get("Item")

        if not item:
            raise HTTPException(status_code=404, detail="Session not found")

        detections = item.get("detections", [])
        print(f"Found {len(detections)} detections")

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "scientific_name",
                "common_name",
                "label",
                "confidence",
                "start_time",
                "end_time",
                "source_filename",
                "source_s3_key",
            ]
        )

        for det in detections:
            writer.writerow(
                [
                    det.get("scientific_name"),
                    det.get("common_name"),
                    det.get("label"),
                    det.get("confidence"),
                    det.get("start_time"),
                    det.get("end_time"),
                    det.get("source_filename"),
                    det.get("source_s3_key"),
                ]
            )
        print(output.getvalue())

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={session_id}.csv"},
        )

    except Exception as e:
        print(f"Error generating CSV for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 1. 辅助函数: Decimal 转 Native (保持不变) ---
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj


# --- 2. ‼️ 新增: 对比逻辑函数 ‼️ ---
def generate_comparison(
    birdnet_list: List[Dict], perch_list: List[Dict]
) -> Dict[str, Any]:
    """
    在内存中对比两个模型的结果，生成并集 (>=1) 和交集 (>=2)。
    """
    merged_map = {}

    # 内部小函数：提取统计信息
    def extract_stats(item):
        return {
            "count": item.get("detection_count", 0),
            "confidence": item.get("avg_confidence", 0),
        }

    # A. 处理 BirdNET 数据
    for item in birdnet_list:
        sci = item["scientific_name"]
        merged_map[sci] = {
            # 基础信息 (复用 BirdNET 的)
            "scientific_name": sci,
            "common_name": item.get("common_name"),
            "iucn": item.get("iucn"),
            "taxonomy": item.get("taxonomy"),
            # 统计
            "birdnet_stats": extract_stats(item),
            "perch_stats": None,  # 暂时为空
            "detected_by": ["birdnet"],
        }

    # B. 处理 Perch 数据 (合并或新增)
    for item in perch_list:
        sci = item["scientific_name"]

        if sci in merged_map:
            # 情况 1: BirdNET 已经发现了 (交集)
            merged_map[sci]["perch_stats"] = extract_stats(item)
            merged_map[sci]["detected_by"].append("perch")
        else:
            # 情况 2: 只有 Perch 发现了 (新增)
            merged_map[sci] = {
                "scientific_name": sci,
                "common_name": item.get("common_name"),
                "iucn": item.get("iucn"),
                "taxonomy": item.get("taxonomy"),
                "birdnet_stats": None,
                "perch_stats": extract_stats(item),
                "detected_by": ["perch"],
            }

    # C. 生成列表

    # 1. 并集 (>= 1 model): 所有被发现的物种
    at_least_one = list(merged_map.values())
    # 按被发现的模型数量排序 (同时被2个发现的排前面)，然后按学名排序
    at_least_one.sort(key=lambda x: (-len(x["detected_by"]), x["scientific_name"]))

    # 2. 交集 (>= 2 models): 同时被两个模型发现
    at_least_two = [item for item in at_least_one if len(item["detected_by"]) >= 2]

    return {
        "detected_by_at_least_one": at_least_one,
        "detected_by_at_least_two": at_least_two,
        "counts": {
            "total_unique_species": len(at_least_one),
            "overlap_species": len(at_least_two),
        },
    }


# --- 3. 修改后的 API 路由 ---
@router.get("/detections-detail")
def get_detections_detail(
    session_id: str,
):  # 注意: FastAPI 建议用 Pydantic model 接收 POST body，这里为了适配你给的代码保持原样
    """
    获取单个分析会话的完整详情。
    后端负责聚合 BirdNET 和 Perch 的数据并生成对比结果。
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        # --- 步骤 1: 获取 Session 元数据 ---
        session_meta_response = table.get_item(Key={"session_id": session_id})
        session_data = session_meta_response.get("Item")

        if not session_data:
            raise HTTPException(
                status_code=404, detail=f"Session with ID {session_id} not found."
            )

        # --- 步骤 2: 获取 Enriched Data (两个列表) ---
        enriched_response = enriched_table.get_item(Key={"session_id": session_id})
        enriched_item = enriched_response.get("Item", {})

        # 从数据库获取原始列表
        birdnet_data = enriched_item.get("birdnet_species", [])
        perch_data = enriched_item.get("perch_species", [])

        # --- ‼️ 步骤 3: 在后端执行对比逻辑 ‼️ ---
        comparison_data = generate_comparison(birdnet_data, perch_data)

        # --- 步骤 4: 组装最终结果 ---
        result_data = {
            "session": session_data,
            "enriched_data": {
                "birdnet": birdnet_data,  # 原始 BirdNET 列表
                "perch": perch_data,  # 原始 Perch 列表
                "comparison": comparison_data,  # 👈 新生成的对比结果
            },
        }

        # 转换 Decimal 并返回
        return {
            "code": 200,
            "message": "Successfully retrieved session details.",
            "data": decimal_to_native(result_data),
        }

    except Exception as e:
        print(f"Error querying session details for {session_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download-npi")
def download_npi_csv(session_id: str):
    """
    Export full NPI report directly from the session table (new structure).
    Uses:
      - session.npi (summary)
      - session.species (list of species rows)
    """
    try:
        # Load session (already enriched by Lambda)
        resp = table.get_item(Key={"session_id": session_id})
        session = resp.get("Item")

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        npi = session.get("npi")
        species_items = session.get("species", [])

        if not npi or not species_items:
            raise HTTPException(
                status_code=404,
                detail="This session does not contain NPI data or species list",
            )

        # Extract session-level metrics
        session_npi = npi.get("score")
        shannon = npi.get("shannon_diversity")
        evenness = npi.get("evenness")
        dominance = npi.get("dominance")
        richness = npi.get("species_richness")
        total_detections = npi.get("total_detections")
        threat_comp = npi.get("threat_composition", {})

        endangered = threat_comp.get("endangered", 0)
        vulnerable = threat_comp.get("vulnerable", 0)
        near_threat = threat_comp.get("near_threat", 0)
        least_concern = threat_comp.get("least_concern", 0)

        # Build species rows (importance_score is precomputed in Lambda)
        species_rows = []
        for sp in species_items:
            species_rows.append(
                [
                    sp.get("scientific_name"),
                    sp.get("common_name"),
                    sp.get("protection_level"),
                    sp.get("detection_count"),
                    round(sp.get("detection_count", 1) / total_detections, 4),
                    sp.get("importance_score", None),
                    sp.get("iucn_url"),
                ]
            )

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Session section
        writer.writerow(["SECTION", "KEY", "VALUE"])
        writer.writerow(["session", "session_id", session_id])
        writer.writerow(["session", "npi_score", session_npi])
        writer.writerow(["session", "species_richness", richness])
        writer.writerow(["session", "total_detections", total_detections])
        writer.writerow(["session", "shannon_diversity", shannon])
        writer.writerow(["session", "evenness", evenness])
        writer.writerow(["session", "dominance_index", dominance])
        writer.writerow(["session", "endangered_species_count", endangered])
        writer.writerow(["session", "vulnerable_species_count", vulnerable])
        writer.writerow(["session", "near_threatened_count", near_threat])
        writer.writerow(["session", "least_concern_count", least_concern])

        writer.writerow([])

        # Species header
        writer.writerow(
            [
                "scientific_name",
                "common_name",
                "protection_level",
                "detection_count",
                "relative_frequency",
                "importance_score",
                "iucn_url",
            ]
        )

        for row in species_rows:
            writer.writerow(row)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={session_id}_NPI.csv"
            },
        )

    except Exception as e:
        print(f"Error generating NPI CSV for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
