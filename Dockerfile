FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py /app/app.py
COPY etag_cache.py /app/etag_cache.py

# Expose port
EXPOSE 8090

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
