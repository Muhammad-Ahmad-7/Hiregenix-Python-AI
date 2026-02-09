# import whisper
# print("hi")
# model = whisper.load_model("tiny")

# res = model.transcribe(r"E:\Project\video-mind\audio.mp3", word_timestamps=True)

# print(res)




from faster_whisper import WhisperModel
from datetime import datetime

# Use "int8" for maximum speed on CPU
model = WhisperModel("base", device="cpu", compute_type="int8")

print("Starting transcription...")
start_time=datetime.now()
segments, info = model.transcribe(r"E:\Project\video-mind\audio_hitesh1hour1.flac", beam_size=1) # beam_size=1 is fastest


# for segment in segments:
#     print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

full_transcription = " ".join(segment.text for segment in segments)
end_time=datetime.now()
print("RESULT", full_transcription)
final_time=end_time-start_time
print("FINAL TIME", final_time)