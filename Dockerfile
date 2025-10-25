FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including distutils
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libx264-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    pkg-config \
    # Add distutils
    python3-distutils \
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

EXPOSE 5005
CMD ["gunicorn", "-b", "0.0.0.0:5005", "-k", "eventlet", "app:app"]
