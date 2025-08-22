FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install requests beautifulsoup4 ics

# Set working directory
WORKDIR /workspace

# Default command
CMD ["python", "src/main.py"]
