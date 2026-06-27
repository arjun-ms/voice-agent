FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (required for PyAudio/webrtc if any, though LiveKit prebuilds wheels usually)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies (strip UTF-8 BOM from requirements.txt if present)
RUN sed '1s/^\xEF\xBB\xBF//' requirements.txt > req.txt
RUN pip install --no-cache-dir -r req.txt

# Copy source code
COPY backend/ /app/backend/
COPY seed.sql /app/
COPY start.sh /app/

# Set Python Path
ENV PYTHONPATH=/app

# Make start script executable
RUN chmod +x /app/start.sh

# Command to run both the FastAPI backend and the LiveKit agent worker
CMD ["/app/start.sh"]
