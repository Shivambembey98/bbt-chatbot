# Stage 1: Build stage
FROM python:3.12-slim as builder

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first for better caching
COPY requirements.txt .

# Install dependencies with minimal cache to reduce space usage
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

# Stage 2: Final stage
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the installed dependencies from the builder stage
COPY --from=builder /usr/local /usr/local

# Copy the entire project into the container
COPY . .

# Expose the Streamlit default port
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "main.py", "--server.maxUploadSize=5", "--server.port=8501", "--server.address=0.0.0.0"]
