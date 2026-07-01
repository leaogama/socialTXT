FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (ffmpeg is required by yt-dlp and faster-whisper)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala o navegador Chromium invisível e suas dependências nativas (necessário para Playwright)
RUN playwright install --with-deps chromium

# Copy the application code
COPY . .

# Expose port 8000 for the web server
EXPOSE 8000

# Start the web server using uvicorn
CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8000"]
