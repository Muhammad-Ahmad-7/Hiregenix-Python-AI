FROM python:3.13-slim

WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["python", "workers/resume_parsing_worker.py"]

