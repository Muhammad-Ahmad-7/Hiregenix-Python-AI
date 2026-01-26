
from config.db import question_result_collection, task_collection
from bson import ObjectId
import subprocess
import whisper
from concurrent.futures import ThreadPoolExecutor
from utils.upload_file import upload_to_cloudinary
import tempfile
import os

def speech_to_text_pipeline(question_result_id: str) -> bool:
    try:
        question_result = question_result_collection.find_one({"_id": ObjectId(question_result_id)})
        print(f" 🔍 Fetched Question Result {question_result_id} from DB: {question_result}")

        if not question_result:
            print("❌ Question Result not found in DB")
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
            transcribed_text = stt_future.result()
            
        print(f"✅ Transcribed Text: {transcribed_text}")
        print(f"✅ Audio URL: {audio_url}")
        
        # DB question result document updated with transcribed text and audio url
        question_result_collection.update_one(
            {"_id": ObjectId(question_result_id)},
            {"$set": {
                "transcriptText": transcribed_text,
                "audioUrl": audio_url,
                "stages": {
                    "sttDone": True,
                    "audioExtracted": True
                }
            }},
            upsert=True
        )
        print(f"✅ Question Result {question_result_id} updated with transcribed text and audio url")
        return True

    except Exception as e:
        print(f"❌ Error processing question result {question_result_id}: {e}")
        return False
    
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
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
    result = model.transcribe(audio_path)
    return result["text"]


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