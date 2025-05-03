# Use the official lightweight Python image
FROM python:3.12-slim
 
# Set the working directory inside the container
WORKDIR /app
 
# Copy the requirements file first for better caching
COPY requirements.txt .
 
# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
 
# Copy the entire project into the container
COPY . .
 
# Expose the Streamlit default port
EXPOSE 8501
 
# Run the application
CMD ["streamlit", "run", "main.py", "--server.maxUploadSize=5", "--server.port=8501", "--server.address=0.0.0.0"]
