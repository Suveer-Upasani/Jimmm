FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for OpenCV, MediaPipe, and aiortc
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create templates directory and copy HTML
RUN mkdir -p templates
COPY templates/index.html templates/

# Expose the Flask/WebRTC port
EXPOSE 5005

# Start the Flask app with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5005", "-k", "eventlet", "app:app"]