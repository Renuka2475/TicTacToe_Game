# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency list first
COPY requirements.txt .

# Install dependencies (FastAPI, Uvicorn, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose port 8000 to access FastAPI
EXPOSE 8000

# Start the FastAPI server when container runs
CMD ["uvicorn", "Server:app", "--host", "0.0.0.0", "--port", "8000"]


