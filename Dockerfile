# Use a clean, optimized Python image as the base layer
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER_ENV=True

# Set up a secure system user to avoid running the browser as root
RUN useradd -m -u 1000 appuser
WORKDIR /app

# Install system dependencies required by Playwright/Chromium architectures
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first to maximize Docker build caching layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install headless Chromium and its explicit system execution libraries
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application files and your logged-in Google profile data
COPY server.py .
COPY --chown=appuser:appuser ./google_session /app/google_session

# Secure application folder permissions
RUN chown -R appuser:appuser /app
USER appuser

# Expose the internal port mapped inside your server.py file
EXPOSE 8080

# Spin up the native FastMCP server configuration instance
CMD ["python", "server.py"]