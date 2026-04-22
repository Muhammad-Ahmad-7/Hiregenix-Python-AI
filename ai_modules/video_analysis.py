import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from config.db import question_result_collection
from bson import ObjectId
from concurrent.futures import ThreadPoolExecutor
import os
import requests
from datetime import datetime



def video_analysis_pipeline(connection, question_result_id: str) -> bool:
    video_path = None
    try:
        question_result = question_result_collection.find_one({"_id": ObjectId(question_result_id)})
        print(f" 🔍 Fetched Question Result {question_result_id} from DB: {question_result}")

        if not question_result:
            print("❌ Question Result not found in DB")
            return False
        
        # Extract audio from the video and update the question result document
        video_url = question_result['videoUrl']
        
        print(f"📷 Processing video URL: {video_url}");
        
        os.makedirs("uploads", exist_ok=True)
        video_path = os.path.join("uploads", f"{question_result_id}_video.webm")
        
        # Downloading the video
        download_result = download_video(video_url, video_path);
        if not download_result:
            raise Exception("Video download failed")
        print(f"✅ Video downloaded at: {video_path}")
        
        result = analyze_interview(connection, video_path)
        print(f"Video Analysis Done\nFinal Result: {result}")
        
        # DB question result document updated with transcribed text and audio url
        question_result_collection.update_one(
            {"_id": ObjectId(question_result_id)},
            {"$set": {
                "videoAnalysis": result,
                "stages.videoAnalyzed": True,
                "updatedAt": datetime.now(),
            }},
            upsert=True
        )
        print(f"✅ Question Result {question_result_id} updated with video analysis json result")
        return True

    except Exception as e:
        print(f"❌ Error processing question result {question_result_id}: {e}")
        raise e
    
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)





def download_video(url: str, local_path: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return True;




# --- Configuration ---
LANDMARK_MODEL = 'ai-models/face_landmarker.task'
DETECTOR_MODEL = 'ai-models/face_detector.task' 
OBJECT_MODEL   = 'ai-models/object_detector.task'

GAZE_THRESHOLD = 0.42 
BLINK_THRESHOLD = 0.5
BANNED_CATEGORIES = ['cell phone', 'laptop', 'book', 'mobile phone']

def analyze_interview(connection, video_path):
    
    print(f"🧠 Loading Models: {LANDMARK_MODEL}, {DETECTOR_MODEL}, {OBJECT_MODEL}")
    # 1. Initialize Face Landmarker (Behavior)
    base_landmarker = python.BaseOptions(model_asset_path=LANDMARK_MODEL)
    landmarker_opts = vision.FaceLandmarkerOptions(
        base_options=base_landmarker,
        running_mode=vision.RunningMode.VIDEO,
        output_face_blendshapes=True,
        num_faces=1
    )
    
    # 2. Initialize Face Detector (Security)
    base_detector = python.BaseOptions(model_asset_path=DETECTOR_MODEL)
    detector_opts = vision.FaceDetectorOptions(
        base_options=base_detector,
        running_mode=vision.RunningMode.VIDEO,
        min_detection_confidence=0.2 
    )

    # 3. Initialize Object Detector (Contraband)
    base_object = python.BaseOptions(model_asset_path=OBJECT_MODEL)
    object_opts = vision.ObjectDetectorOptions(
        base_options=base_object,
        running_mode=vision.RunningMode.VIDEO,
        score_threshold=0.3,
        category_allowlist=BANNED_CATEGORIES
    )
    
    # Create Task Instances
    landmarker = vision.FaceLandmarker.create_from_options(landmarker_opts)
    detector = vision.FaceDetector.create_from_options(detector_opts)
    obj_detector = vision.ObjectDetector.create_from_options(object_opts)
    
    cap = cv2.VideoCapture(video_path)
    
    stats = {
        "gaze_v_secs": 0, "multi_face_secs": 0, "no_face_secs": 0,
        "object_v_secs": 0, "total_frames": 0, "prev_s": 0, "last_ts": 0,
        "total_smiles": 0, "blink_count": 0, "posture_v_secs": 0
    }
    
    gaze_start = None
    eye_closed = False

    print(f"--- Launching Triple-Model Audit: {video_path} ---")

    while cap.isOpened():
        connection.process_data_events()  # Keep RabbitMQ connection alive
        success, frame = cap.read()
        if not success: break

        ts_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        curr_s = ts_ms / 1000.0
        frame_duration = curr_s - stats["prev_s"]
        stats["prev_s"] = curr_s
        stats["last_ts"] = curr_s

        # Convert to MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # --- TASK 1: OBJECT DETECTION ---
        obj_result = obj_detector.detect_for_video(mp_image, ts_ms)
        if obj_result.detections:
            stats["object_v_secs"] += frame_duration

        # --- TASK 2: FACE COUNT (SECURITY) ---
        detection_result = detector.detect_for_video(mp_image, ts_ms)
        num_faces = len(detection_result.detections) if detection_result.detections else 0

        if num_faces > 1: stats["multi_face_secs"] += frame_duration
        if num_faces == 0: stats["no_face_secs"] += frame_duration

        # --- TASK 3: BEHAVIOR & GAZE (LANDMARKS) ---
        if num_faces == 1:
            landmark_result = landmarker.detect_for_video(mp_image, ts_ms)
            if landmark_result.face_blendshapes:
                blend = {s.category_name: s.score for s in landmark_result.face_blendshapes[0]}
                
                # Gaze Logic
                is_looking_away = any(val > GAZE_THRESHOLD for key, val in blend.items() if "eyeLook" in key)
                if is_looking_away:
                    if gaze_start is None: gaze_start = curr_s
                else:
                    if gaze_start:
                        if (curr_s - gaze_start) >= 0.5: stats["gaze_v_secs"] += (curr_s - gaze_start)
                        gaze_start = None

                # Blinking (Stress)
                is_blinking = (blend['eyeBlinkLeft'] + blend['eyeBlinkRight']) / 2 > BLINK_THRESHOLD
                if is_blinking and not eye_closed:
                    stats["blink_count"] += 1
                    eye_closed = True
                elif not is_blinking:
                    eye_closed = False

                # Confidence (Smiles)
                if blend['mouthSmileLeft'] > 0.4 or blend['mouthSmileRight'] > 0.4:
                    stats["total_smiles"] += 1

                # Posture/Stress (Brow Furrowing)
                if blend['browDownLeft'] > 0.5 or blend['browDownRight'] > 0.5:
                    stats["posture_v_secs"] += frame_duration

        stats["total_frames"] += 1

    cap.release()
    
    print(f"--- Video Analysis Done => Now calculating results---")

    # --- RESULTS PROCESSING ---
    duration = stats["last_ts"]
    blink_rate = (stats["blink_count"] / duration) * 60 if duration > 0 else 0
    
    # Weighted Integrity Score
    # Penalty: Objects > Multi-face > Absence > Gaze
    penalties = (stats["object_v_secs"] * 1.5) + stats["multi_face_secs"] + (stats["no_face_secs"] * 0.5) + (stats["gaze_v_secs"] * 0.3)
    integrity_score = max(0, round(100 - (penalties / duration * 100), 2))

    # Confidence calculation
    base_conf = (stats["total_smiles"] / stats["total_frames"] * 500) + 50
    final_conf = min(100, max(0, base_conf - (stats["posture_v_secs"] / duration * 100)))

    return {
        "integrity_report": {
            "integrity_score": integrity_score,
            "banned_object_detection_secs": round(stats["object_v_secs"], 2),
            "unauthorized_person_secs": round(stats["multi_face_secs"], 2),
            "candidate_absence_secs": round(stats["no_face_secs"], 2)
        },
        "behavioral_report": {
            "confidence_score": round(final_conf, 2),
            "stress_indicator_blink_rate": f"{round(blink_rate, 1)} bpm",
            "gaze_distraction_secs": round(stats["gaze_v_secs"], 2),
            "facial_stress_secs": round(stats["posture_v_secs"], 2)
        }
    }




# if __name__ == "__main__":
#     report = analyze_interview('uploads/video1.webm')
#     import json
#     print(json.dumps(report, indent=4))