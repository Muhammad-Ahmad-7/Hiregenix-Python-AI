FROM python:3.11.9-slim

# Install system dependencies
# ffmpeg: for Whisper/Audio processing
# libsm6/libxext6: for MediaPipe/OpenCV
# libmagic1/libjpeg-dev: for ReportLab/PDF images
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libmagic1 \
    libjpeg-dev \
    libfreetype6-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "workers.resume_parsing_worker.py"]

