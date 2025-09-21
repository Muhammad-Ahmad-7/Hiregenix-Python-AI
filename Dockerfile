FROM python:3.11

WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["python", "workers/worker_resume.py"]

