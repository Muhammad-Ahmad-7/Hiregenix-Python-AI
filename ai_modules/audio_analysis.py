from config.db import question_result_collection, task_collection
from bson import ObjectId
import subprocess
from concurrent.futures import ThreadPoolExecutor
from utils.upload_file import upload_to_cloudinary
import tempfile
import os
from typing import List, Dict
import numpy as np
import requests
import os
import numpy as np
import librosa
import requests
from datetime import datetime


def audio_analysis_pipeline(question_result_id: str) -> bool:
    audio_path=None
    try:
        question_result = question_result_collection.find_one({"_id": ObjectId(question_result_id)})
        print(f" 🔍 Fetched Question Result {question_result_id} from DB: {question_result}")
        if not question_result:
            print("❌ Question Result not found in DB")
            return False
        print("✅ Question Result found in DB")
        audio_url = question_result['audioUrl']
        print(f"🎤 Processing audio URL: {audio_url}")
        
        os.makedirs("temp", exist_ok=True)
        audio_path = os.path.join("temp", f"{question_result_id}_audio.mp3")
        download_result = download_audio(audio_url,audio_path)
        if not download_result:
            return False
        print(f"✅ Audio downloaded at: {audio_path}")
        
        stt_data = question_result['sttData']
        final_result = analyze_audio(audio_path,stt_data)
        print(f"✅ Audio Analysis: {final_result}")
        
        # DB question result document updated with audio analysis data
        question_result_collection.update_one(
            {"_id": ObjectId(question_result_id)},
            {"$set": {
                "audioAnalysis": final_result,
                "stages.audioAnalyzed": True,
                "updatedAt": datetime.now(),
            }},
            upsert=True
        )
        print(f"✅ Question Result {question_result_id} updated with audio analysis data stored.")
        return True
    except Exception as e:
        print(f"❌ Error processing question result {question_result_id}: {e}")
        return False
    
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)




def download_audio(url: str, filename:str) -> str:
    """Download audio from a URL and save locally."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)
    return True



def analyze_audio(audio_path, stt_data):
    # --- Load audio ---
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    
    # --- WORDS & SPEECH ---
    all_words = stt_data.get('words', [])
    word_count = len(all_words)
    
    # Active speech time
    active_speech_time = sum([w['end'] - w['start'] for w in all_words])
    
    # Pace
    raw_wpm = (word_count / duration) * 60 if duration > 0 else 0
    effective_wpm = (word_count / active_speech_time) * 60 if active_speech_time > 0 else 0
    speech_ratio = active_speech_time / duration if duration > 0 else 0

    # --- PAUSES ---
    pauses = []
    for i in range(len(all_words) - 1):
        gap = all_words[i+1]['start'] - all_words[i]['end']
        if gap >= 0.3:  # meaningful pause threshold
            pauses.append(gap)
    avg_pause = float(np.mean(pauses)) if pauses else 0.0
    max_pause = float(max(pauses)) if pauses else 0.0
    long_pauses = [p for p in pauses if p > 2.0]

    # --- FILLERS ---
    filler_words = ["um", "uh", "ah", "like", "hmmm"]
    multi_word_fillers = ["you know", "i mean", "sort of", "kind of"]
    
    transcript = stt_data.get('text', '').lower()
    detected_single = sum(1 for w in all_words if w['text'].lower().strip(',.') in filler_words)
    detected_multi = sum(transcript.count(f) for f in multi_word_fillers)
    filler_count = detected_single + detected_multi
    filler_per_minute = (filler_count / duration) * 60 if duration > 0 else 0.0

    # --- PITCH ---
    f0 = librosa.yin(y, fmin=50, fmax=500)  # human speech range
    f0 = f0[~np.isnan(f0)]
    f0 = f0[(f0 >= 50) & (f0 <= 500)]  # filter any outliers
    pitch_mean = float(np.mean(f0)) if len(f0) > 0 else 0.0
    pitch_median = float(np.median(f0)) if len(f0) > 0 else 0.0
    pitch_std = float(np.std(f0)) if len(f0) > 0 else 0.0
    pitch_range = float(np.ptp(f0)) if len(f0) > 0 else 0.0

    # --- LOUDNESS ---
    rms = librosa.feature.rms(y=y)[0]
    db_rms = librosa.amplitude_to_db(rms, ref=np.max)
    loudness_avg = float(np.mean(db_rms))
    loudness_std = float(np.std(db_rms))

    # --- QUALITY (SNR & Clipping) ---
    noise_floor = np.percentile(rms, 10)
    snr_estimate = float(20 * np.log10((np.mean(rms) + 1e-8) / (noise_floor + 1e-8)))
    clipping_count = int(np.sum(np.abs(y) >= 0.99))

    # --- COMPOSE METRICS ---
    return {
        "audio_metrics": {
            "pace": {
                "raw_wpm": round(float(raw_wpm), 2),
                "effective_wpm": round(float(effective_wpm), 2),
                "speech_ratio": round(float(speech_ratio), 2)
            },
            "pauses": {
                "pause_count": int(len(pauses)),
                "avg_pause_sec": round(avg_pause, 2),
                "max_pause_sec": round(max_pause, 2),
                "long_pause_count": int(len(long_pauses))
            },
            "fillers": {
                "filler_count": int(filler_count),
                "filler_per_minute": round(float(filler_per_minute), 2)
            },
            "pitch": {
                "mean": round(pitch_mean, 2),
                "median": round(pitch_median, 2),
                "std": round(pitch_std, 2),
                "range": round(pitch_range, 2)
            },
            "loudness": {
                "avg": round(loudness_avg, 2),
                "std": round(loudness_std, 2)
            },
            "quality": {
                "snr_estimate": round(snr_estimate, 2),
                "clipping": clipping_count
            }
        }
    }