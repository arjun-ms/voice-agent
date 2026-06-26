FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (required for PyAudio/webrtc if any, though LiveKit prebuilds wheels usually)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Install dependencies (Handling potential UTF-16 encoding in requirements.txt from Windows)
RUN iconv -f UTF-16 -t UTF-8 requirements.txt > req.txt || cp requirements.txt req.txt
RUN pip install --no-cache-dir -r req.txt

# Copy source code
COPY backend/ /app/backend/
COPY seed.sql /app/

# Set Python Path
ENV PYTHONPATH=/app

# Command to run the agent worker
CMD ["python", "backend/voice_agent.py", "start"]
