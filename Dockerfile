# Use a clean, optimized Python image as the base layer
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER_ENV=True

# Pin Playwright's browser cache to a fixed, shared path instead of the
# default ~/.cache/ms-playwright. The default resolves relative to whichever
# user runs `playwright install`, which here is root (since USER appuser is
# set later, after the install). At runtime the app runs as appuser, whose
# own home directory cache is empty, so Chromium "isn't installed" from its
# point of view even though root's copy exists. A fixed, explicit path
# sidesteps whose home directory it is entirely -- this must be set before
# both the install step below and before the app runs.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

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

# Install headless Chromium and its explicit system execution libraries.
# These land under PLAYWRIGHT_BROWSERS_PATH (set above), not root's home.
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application files and your logged-in Google profile data
COPY server.py .
COPY --chown=appuser:appuser ./google_session /app/google_session

# Secure application folder permissions, and hand the shared browser cache
# to appuser too -- otherwise appuser can see the directory but can't
# execute the browser binary inside it.
RUN chown -R appuser:appuser /app /ms-playwright
USER appuser

# Expose the internal port mapped inside your server.py file
EXPOSE 8080

# Spin up the native FastMCP server configuration instance
CMD ["python", "server.py"]