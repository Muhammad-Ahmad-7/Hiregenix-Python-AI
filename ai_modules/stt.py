
from config.db import question_result_collection, task_collection
from bson import ObjectId
import subprocess
import whisper
from concurrent.futures import ThreadPoolExecutor
from utils.upload_file import upload_to_cloudinary
import tempfile
import os
from typing import List, Dict
import numpy as np
from datetime import datetime

def speech_to_text_pipeline(question_result_id: str) -> bool:
    video_path=None
    audio_path=None
    try:
        question_result = question_result_collection.find_one({"_id": ObjectId(question_result_id)})
        print(f" 🔍 Fetched Question Result {question_result_id} from DB: {question_result}")

        if not question_result:
            print("❌ Question Result not found in DB")
            return False
        print("✅ Question Result found in DB")
        
        if question_result["stages"]["sttDone"] and question_result['stages']['audioExtracted']:
            print(f"✅ Question Result {question_result_id} already processed")
            return False
        
        # Extract audio from the video and update the question result document
        video_url = question_result['videoUrl']
        
        print(f"🎤 Processing video URL: {video_url}");
        
        os.makedirs("temp", exist_ok=True)
        video_path = os.path.join("temp", f"{question_result_id}_input.webm")
        audio_path = os.path.join("temp", f"{question_result_id}_output.mp3")
        
        # Downloading the video
        download_result = download_video(video_url, video_path);
        if not download_result:
            return False
        print(f"✅ Video downloaded at: {video_path}")
        
        # Extracting audio from the video
        extracted_audio_path = extract_audio_from_video(video_url, audio_path)
        if not extracted_audio_path:
            return False
        print(f"✅ Audio extracted at: {extracted_audio_path}")

        audio_url = ""
        transcribed_text = ""
        # Extracting speech to text from the audio
        with ThreadPoolExecutor() as executor:
            cloud_future = executor.submit(upload_to_cloudinary, extracted_audio_path)
            stt_future = executor.submit(extract_stt, audio_path)
            
            audio_url = cloud_future.result()
            sttData = stt_future.result()
            
        print(f"✅ Transcribed Text: {sttData}")
        print(f"✅ Audio URL: {audio_url}")
        
        # DB question result document updated with transcribed text and audio url
        question_result_collection.update_one(
            {"_id": ObjectId(question_result_id)},
            {"$set": {
                "sttData": sttData,
                "audioUrl": audio_url,
                "stages.sttDone": True,
                "stages.audioExtracted": True,
                "updatedAt": datetime.now(),
            }},
            upsert=True
        )
        print(f"✅ Question Result {question_result_id} updated with transcribed text and audio url")
        return True

    except Exception as e:
        print(f"❌ Error processing question result {question_result_id}: {e}")
        return False
    
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)



def extract_audio_from_video(video_url: str, output_audio_path: str) -> bool:
    """
    Extract audio from video using ffmpeg.
    Returns the path to the audio file.
    """
    try:
        command = ["ffmpeg", "-i", video_url, "-vn", "-acodec", "mp3", "-y", output_audio_path]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✅ Audio extracted to {output_audio_path}")
        return output_audio_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Error extracting audio: {e}")
        return False


model = whisper.load_model("small")
def extract_stt(audio_path: str) -> str:
    result = model.transcribe(audio_path, word_timestamps=True)
    result = clean_whisper_output(result)
    return result


def convert_float(value):
    if isinstance(value, np.floating):
        return float(value)
    return value

def clean_whisper_output(raw_whisper: Dict) -> Dict:
    """
    Cleans Whisper output so it is fully JSON-serializable and structured for MongoDB.
    Converts all numpy floats to regular floats and strips unnecessary spaces.
    
    Args:
        raw_whisper (Dict): Raw Whisper output.
    
    Returns:
        Dict: Cleaned structure with 'text', 'segments', and 'words'.
    """
    def convert_float(value):
        if isinstance(value, np.floating):
            return float(value)
        return value

    transcript = raw_whisper.get("text", "").strip()

    cleaned_segments: List[Dict] = []

    for seg in raw_whisper.get("segments", []):
        seg_text = seg.get("text", "").strip()
        start = convert_float(seg.get("start", 0.0))
        end = convert_float(seg.get("end", 0.0))

        cleaned_words = []
        for w in seg.get("words", []):
            word_text = w.get("word", "").strip()
            if not word_text:
                continue
            word_obj = {
                "word": word_text,
                "start": convert_float(w.get("start")),
                "end": convert_float(w.get("end")),
            }
            cleaned_words.append(word_obj)

        cleaned_segments.append({
            "text": seg_text,
            "start": start,
            "end": end,
            "words": cleaned_words
        })

    return {
        "transcript": transcript,
        "segments": cleaned_segments,
    }

# def stt(url: str):
#     res = model.transcribe(url, word_timestamps=True)
#     print(clean_whisper_output(res))

import requests
from pathlib import Path

def download_video(url: str, local_path: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return True;