import io
import requests
import librosa
import numpy as np
import parselmouth
import json

# ------------------------------
# 1️⃣ Audio & Feature Extraction
# ------------------------------
def load_audio_segment(audio_url, start_sec, end_sec, sr=None):
    try:
        print(f"Loading audio segment {start_sec:.2f}s to {end_sec:.2f}s...")
        response = requests.get(audio_url)
        response.raise_for_status()
        audio_bytes = io.BytesIO(response.content)
        y, sr = librosa.load(audio_bytes, sr=sr, mono=True, offset=start_sec, duration=end_sec-start_sec)
        duration = len(y)/sr
        print(f"Segment loaded, duration: {duration:.2f}s, sample rate: {sr}")
        return y, sr, duration
    except Exception as e:
        print(f"[Warning] Failed to load segment: {e}")
        return np.zeros(100), 22050, 0.01  # minimal dummy audio

def extract_features_segment(y, sr):
    try:
        sound = parselmouth.Sound(y, sampling_frequency=sr)

        # Pitch
        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array['frequency']
        pitch_values = pitch_values[pitch_values != 0]
        pitch_mean = np.mean(pitch_values) if len(pitch_values) > 0 else 0
        pitch_var = np.var(pitch_values) if len(pitch_values) > 0 else 0
        pitch_range = pitch_values.max()-pitch_values.min() if len(pitch_values) > 0 else 0

        # Intensity
        intensity = sound.to_intensity()
        intensity_values = intensity.values.flatten() if intensity.values.size > 0 else np.array([0])
        intensity_mean = intensity_values.mean()
        intensity_var = intensity_values.var()

        # Jitter & Shimmer
        try:
            pp = parselmouth.praat.call(sound, "To PointProcess (periodic, cc)", 75, 500)
            jitter = parselmouth.praat.call(pp, "Get jitter (local)", 0.0001, 0.02, 1.3, 1.6)
            shimmer = parselmouth.praat.call([sound, pp], "Get shimmer (local)", 0.0001, 0.02, 1.3, 1.6, 1.0)
        except:
            jitter = shimmer = 0

        # HNR
        try:
            hnr = parselmouth.praat.call(sound, "Get harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        except:
            hnr = 0

        # Silence proportion
        silence_threshold = 0.01
        silent_samples = np.sum(intensity_values < intensity_values.max()*silence_threshold)
        silence_ratio = silent_samples / len(intensity_values)

        print(f"Extracted features: pitch_var={pitch_var:.2f}, intensity_mean={intensity_mean:.2f}, jitter={jitter:.5f}, shimmer={shimmer:.5f}, HNR={hnr:.2f}, silence_ratio={silence_ratio:.2f}")

        return {
            "pitch_mean": pitch_mean,
            "pitch_var": pitch_var,
            "pitch_range": pitch_range,
            "intensity_mean": intensity_mean,
            "intensity_var": intensity_var,
            "jitter": jitter,
            "shimmer": shimmer,
            "hnr": hnr,
            "silence_ratio": silence_ratio
        }
    except Exception as e:
        print(f"[Warning] Failed to extract features: {e}")
        return {
            "pitch_mean":0,"pitch_var":0,"pitch_range":0,
            "intensity_mean":0,"intensity_var":0,
            "jitter":0,"shimmer":0,"hnr":0,"silence_ratio":0
        }

# ------------------------------
# 2️⃣ Segment scoring
# ------------------------------
def score_segment(features, segment_text, duration_sec):
    words = segment_text.split()
    wps = len(words)/duration_sec if duration_sec > 0 else 0

    fluency = np.clip((wps/4)*10 * (1 - features['silence_ratio']), 0, 10)
    confidence_raw = (1 / (1 + features['jitter'] + features['shimmer'])) * (1 - features['silence_ratio']) * 10
    confidence = np.clip(confidence_raw, 0, 10)
    pron_raw = features['hnr'] / 30 * 5 + (1 / (1 + features['jitter'] + features['shimmer'])) * 5
    pronunciation = np.clip(pron_raw, 0, 10)
    emotion_raw = ((features['pitch_range']/200) + (features['intensity_var']/1000)) * 5
    emotion = np.clip(emotion_raw, 0, 10)

    print(f"Segment scoring: Fluency={fluency:.2f}, Confidence={confidence:.2f}, Pronunciation={pronunciation:.2f}, Emotion={emotion:.2f}")

    return {
        "fluency": round(fluency,2),
        "confidence": round(confidence,2),
        "pronunciation": round(pronunciation,2),
        "emotion": round(emotion,2),
        "duration": duration_sec
    }

# ------------------------------
# 3️⃣ Aggregate segments
# ------------------------------
def aggregate_segments(segment_scores):
    total_duration = sum(s['duration'] for s in segment_scores)
    if total_duration == 0:
        return {"fluency":0,"confidence":0,"pronunciation":0,"emotion":0,"overall":0}

    agg = {}
    for key in ['fluency','confidence','pronunciation','emotion']:
        weighted = sum(s[key]*s['duration'] for s in segment_scores)/total_duration
        agg[key] = round(weighted,2)

    overall = 0.35*agg['fluency'] + 0.3*agg['confidence'] + 0.25*agg['pronunciation'] + 0.1*agg['emotion']
    agg['overall'] = round(np.clip(overall, 0, 10),2)

    print("\nAggregated results:")
    print(f"Fluency={agg['fluency']}, Confidence={agg['confidence']}, Pronunciation={agg['pronunciation']}, Emotion={agg['emotion']}, Overall={agg['overall']}\n")
    return agg

# ------------------------------
# 4️⃣ Main Pipeline
# ------------------------------
def analyze_candidate_audio_whisper(audio_url, whisper_json):
    print("Starting analysis of candidate audio...\n")
    segment_scores = []
    for idx, seg in enumerate(whisper_json.get('segments', [])):
        start, end, text = seg.get('start',0), seg.get('end',0), seg.get('text','').strip()
        if len(text) == 0 or end-start <= 0.01:
            continue
        print(f"\nProcessing segment {idx+1}: '{text[:50]}...' ({start:.2f}s -> {end:.2f}s)")
        y, sr, duration = load_audio_segment(audio_url, start, end)
        features = extract_features_segment(y, sr)
        seg_score = score_segment(features, text, duration)
        segment_scores.append(seg_score)

    return aggregate_segments(segment_scores)

# ------------------------------
# 5️⃣ Example usage
# ------------------------------
if __name__ == "__main__":
    audio_url = "https://res.cloudinary.com/hiregenx/video/upload/v1769427469/ivkiwf3limvam9fje7w0.mp3"

    # Load Whisper JSON
    try:
        with open("whisper_output1.json","r") as f:
            whisper_json = json.load(f)
    except Exception as e:
        print(f"[Error] Could not load Whisper JSON: {e}")
        whisper_json = {"segments": []}

    final_result = analyze_candidate_audio_whisper(audio_url, whisper_json)
    print("Final Result:", json.dumps(final_result, indent=4))
