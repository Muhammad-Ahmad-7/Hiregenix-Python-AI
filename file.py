import whisper


def extract_stt(audio_path: str) -> str:
    model = whisper.load_model("small")
    result = model.transcribe(audio_path)
    print(result)
    return result["text"]

extract_stt("https://res.cloudinary.com/hiregenx/video/upload/v1769427469/ivkiwf3limvam9fje7w0.mp3")
