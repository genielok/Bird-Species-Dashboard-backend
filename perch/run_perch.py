# # run_perch.py
# import os, sys, json, boto3, subprocess
# import librosa
# import numpy as np
# import tensorflow as tf

# # 关键：导入 perch_hoplite 库
# from perch_hoplite.zoo import model_configs

# print("--- PERCH WORKER (perch_hoplite): v1.0 ---")

# # --- 1. 配置 ---
# INPUT_BUCKET = os.environ.get("S3_BUCKET_NAME")
# PROJECT_NAME = os.environ.get("PROJECT_NAME", "unknown")
# OUTPUT_PREFIX = os.environ.get("S3_OUTPUT_PREFIX", "results/perch") 
# INPUT_KEYS_JSON = os.environ.get("S3_INPUT_KEYS")
# MIN_CONFIDENCE = 0.25 # 你可以调整这个阈值

# try:
#     INPUT_KEYS = [obj["key"] for obj in json.loads(INPUT_KEYS_JSON)]
# except Exception as e:
#     print(f"FATAL: Could not parse S3_INPUT_KEYS JSON: {e}")
#     sys.exit(1)

# s3_client = boto3.client("s3")
# TEMP_DIR = "/tmp/perch_work"
# os.makedirs(TEMP_DIR, exist_ok=True)

# # --- 2. 在全局加载模型 (只加载一次) ---
# try:
#     print("Loading Perch model (perch_v2_cpu)...")
#     # 'perch_v2_cpu' 是 Fargate (无 GPU) 的正确选择
#     # 这会自动从 Kaggle/TF Hub 下载模型
#     model = model_configs.load_model_by_name('perch_v2_cpu')
#     class_list = model.class_list # 获取模型对应的标签列表
#     print(f"Perch model loaded. {len(class_list)} classes.")
# except Exception as e:
#     print(f"FATAL: Could not load Perch model: {e}")
#     sys.exit(1)


# # --- 3. 单个文件的处理函数 ---
# def process_single_file(key: str):
#     local_filename = os.path.basename(key)
#     local_audio_path = os.path.join(TEMP_DIR, local_filename)
#     local_result_path = os.path.join(TEMP_DIR, f"{local_filename}.json")

#     try:
#         print(f"[Perch] Downloading s3://{INPUT_BUCKET}/{key} ...")
#         s3_client.download_file(INPUT_BUCKET, key, local_audio_path)

#         # 1. 使用 Librosa 加载音频
#         waveform, original_sample_rate = librosa.load(local_audio_path, sr=None, mono=True)
        
#         # 2. 将音频重采样 (Resample) 到模型所需的 32kHz
#         if original_sample_rate != model.sample_rate:
#             waveform = librosa.resample(waveform, orig_sr=original_sample_rate, target_sr=model.sample_rate)
        
#         # 3. 运行模型推理
#         # perch_hoplite 会自动处理 5 秒的窗口 (windowing)
#         print(f"[Perch] Running inference on {key}...")
#         outputs = model.embed(waveform)
        
#         # outputs.logits['label'] 的形状是 [num_windows, num_classes]
#         logits = outputs.logits['label']
        
#         # 将 Logits 转换为 0-1 之间的概率分数
#         scores = tf.nn.softmax(logits).numpy()
        
#         detections = []
        
#         # 4. 遍历每个时间窗口的结果
#         for window_index, window_scores in enumerate(scores):
            
#             # 找到这个窗口中所有分数 > 阈值的鸟类
#             high_score_indices = np.where(window_scores > MIN_CONFIDENCE)[0]
            
#             for class_index in high_score_indices:
#                 confidence = float(window_scores[class_index])
#                 # 从模型加载的 class_list 中获取名字
#                 species_name = class_list[class_index] 
                
#                 detections.append({
#                     "scientific_name": species_name, # Perch v2 主要使用 eBird scientific_name
#                     "common_name": species_name, # 你可能需要一个映射表来转为 common_name
#                     "confidence": confidence,
#                     "start_time": window_index * 5.0, # Perch 使用 5s 窗口
#                     "end_time": (window_index + 1) * 5.0,
#                     "model_version": "perch_v2_cpu"
#                 })

#         # 5. 保存 JSON 结果 (和 birdnet 脚本一样)
#         result_json = {
#             "source_bucket": INPUT_BUCKET,
#             "source_key": key,
#             "analysis_model": "Perch",
#             "total_detections": len(detections),
#             "detections": detections
#         }
        
#         with open(local_result_path, "w") as f:
#             json.dump(result_json, f, indent=2)

#         result_key = f"{OUTPUT_PREFIX}/{local_filename}.json"
#         s3_client.upload_file(local_result_path, INPUT_BUCKET, result_key)
#         print(f"✅ [Perch] Uploaded result: s3://{INPUT_BUCKET}/{result_key}")
#         return result_key
    
#     except Exception as e:
#         print(f"❌ [Perch] Failed processing {key}: {e}")
#         import traceback
#         traceback.print_exc()
#         return None
#     finally:
#         # 清理临时文件
#         for path in [local_audio_path, local_result_path]:
#             if os.path.exists(path):
#                 os.remove(path)

# # --- 4. 脚本入口 ---
# if __name__ == "__main__":
#     print(f"--- Perch Task Started ({len(INPUT_KEYS)} files) ---")
    
#     all_results = []
#     for key in INPUT_KEYS:
#         result = process_single_file(key)
#         if result:
#             all_results.append(result)

#     print(f"--- Completed {len(all_results)}/{len(INPUT_KEYS)} files ---")
#     print("--- Perch Task Complete ---")
#     # 这个脚本不需要打印 JSON 到 stdout



from perch_hoplite.zoo import model_configs
import numpy as np

# Input: 5 seconds of silence as mono 32 kHz waveform samples.
waveform = np.zeros(5 * 32000, dtype=np.float32)

# Automatically downloads the model from Kaggle.
model = model_configs.load_model_by_name('perch_v2')

outputs = model.embed(waveform)
# do something with outputs.embeddings and outputs.logits['label']
