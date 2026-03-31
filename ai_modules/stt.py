
from config.db import question_result_collection
from bson import ObjectId
import subprocess
from utils.upload_file import upload_to_cloudinary
import os
import numpy as np
from datetime import datetime
from config.env import ASSEMBLY_AI_API_KEY
import assemblyai as aai
import requests

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

        audio_url = upload_to_cloudinary(extracted_audio_path)
        sttData = extract_stt(audio_path=audio_url)
            
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



def extract_stt(audio_path: str) -> str:
    """Extract speech to text from assemblyai API."""
    try:
        aai.settings.api_key = ASSEMBLY_AI_API_KEY
        config = aai.TranscriptionConfig(speech_models=["universal-3-pro"], language_code="en", sentiment_analysis=True)

        transcript = aai.Transcriber(config=config).transcribe(audio_path)

        if transcript.status == "error":
            raise RuntimeError(f"Transcription failed: {transcript.error}")

        clean_segments = []

        for seg in transcript.json_response['sentiment_analysis_results']:
            # print(seg)
            clean_segments.append({
                "text": seg['text'],
                "start": seg['start'] / 1000,  # convert ms → seconds (optional)
                "end": seg['end'] / 1000,
                "confidence": seg['confidence'],
                "sentiment": seg['sentiment'].value  # IMPORTANT
            })

        result = {
            "text": transcript.text,
            "confidence": transcript.confidence,
            "segments": clean_segments
        }
        return result
    except Exception as e:
        print(f"❌ Error extracting speech to text: {e}")
        return False


def download_video(url: str, local_path: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return True;