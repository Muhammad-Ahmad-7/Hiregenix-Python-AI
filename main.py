# Install the assemblyai package by executing the command "pip install assemblyai"

import assemblyai as aai

aai.settings.api_key = "22e34df3c3924ff3b6386b7875483254"

# audio_file = "./local_file.mp3"
audio_file = "https://res.cloudinary.com/hiregenx/video/upload/v1772614431/pmpyztqyk5a7kn1jdelr.mp3"

# Uses universal-3-pro for en, es, de, fr, it, pt. Else uses universal-2 for support across all other languages
config = aai.TranscriptionConfig(speech_models=["universal-3-pro"], language_code="en", sentiment_analysis=True)

transcript = aai.Transcriber(config=config).transcribe(audio_file)

if transcript.status == "error":
  raise RuntimeError(f"Transcription failed: {transcript.error}")

# print(transcript.json_response)

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

print(result)