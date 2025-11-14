import os
import sys
import boto3
import json
import uuid
import warnings
from datetime import datetime
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer

print("--- RUNNING VERSION: no-ffmpeg-convert-v2 ---")

# -----------------------------------------------------------------
# 1. Configuration (from environment variables)
# -----------------------------------------------------------------
INPUT_BUCKET = os.environ.get("S3_BUCKET_NAME")
OUTPUT_PREFIX = os.environ.get("S3_OUTPUT_PREFIX", "results/birdnet")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "unknown")
os.environ["AUDIOMIXER_BACKEND"] = "ffmpeg"

INPUT_KEYS_JSON = os.environ.get("S3_INPUT_KEYS")
if not INPUT_BUCKET or not INPUT_KEYS_JSON:
    print("FATAL: S3_BUCKET_NAME and S3_INPUT_KEYS must be set in environment.")
    sys.exit(1)

try:
    INPUT_KEYS = [obj["key"] for obj in json.loads(INPUT_KEYS_JSON)]
except Exception as e:
    print(f"FATAL: Could not parse S3_INPUT_KEYS JSON: {e}")
    sys.exit(1)

TEMP_DIR = "/tmp/birdnet_work"
os.makedirs(TEMP_DIR, exist_ok=True)

s3_client = boto3.client("s3")
analyzer = Analyzer()  # Load once globally

import subprocess


# -----------------------------------------------------------------
# 2. Core Processing Function (for one file)
# -----------------------------------------------------------------
def process_single_file(key: str):
    local_filename = os.path.basename(key)
    local_audio_path = os.path.join(TEMP_DIR, local_filename)
    local_result_path = os.path.join(TEMP_DIR, f"{local_filename}.json")

    try:
        print(f"Downloading s3://{INPUT_BUCKET}/{key} ...")
        s3_client.download_file(INPUT_BUCKET, key, local_audio_path)

        if os.path.getsize(local_audio_path) < 1024:
            raise ValueError(f"File {key} is empty or corrupted (size < 1KB)")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            recording = Recording(
                analyzer=analyzer,
                path=local_audio_path,
                date=datetime.now(),
                min_conf=0.25,
            )
            print("read_audio_data")
            recording.analyze()
            print(
                f"read_audio_data: complete, read {len(recording.detections)} detections"
            )

        detections = []
        print(recording.detections)
        for det in recording.detections:
            det['id'] = str(uuid.uuid4())
            det['model_version'] = analyzer.version
            det['source_s3_key'] = key
            det['source_filename'] = local_filename
            detections.append(det)

        result_json = {
            "source_bucket": INPUT_BUCKET,
            "source_key": key,
            "analysis_model": "BirdNET",
            "total_detections": len(detections),
            "detections": detections,
        }

        with open(local_result_path, "w") as f:
            json.dump(result_json, f, indent=2)

        result_key = f"{OUTPUT_PREFIX}/{local_filename}.json"
        s3_client.upload_file(local_result_path, INPUT_BUCKET, result_key)
        print(f"✅ ======= Uploaded result: s3://{INPUT_BUCKET}/{result_key}")
        return result_key

    except Exception as e:
        print(f"❌ Failed processing {key}: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        for path in [local_audio_path, local_result_path]:
            if os.path.exists(path):
                os.remove(path)


# -----------------------------------------------------------------
# 3. Entrypoint
# -----------------------------------------------------------------
if __name__ == "__main__":
    print(f"--- BirdNET Batch Processing Task Started ({len(INPUT_KEYS)} files) ---")

    all_results = []
    for key in INPUT_KEYS:
        result = process_single_file(key)
        if result:
            all_results.append(result)

    print(f"--- Completed {len(all_results)}/{len(INPUT_KEYS)} files ---")

    summary = {
        "project": PROJECT_NAME,
        "processed_files": len(all_results),
        "result_keys": all_results,
    }
    print(json.dumps(summary))
