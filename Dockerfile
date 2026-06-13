FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + static dashboard
COPY backend/app ./app
COPY backend/static ./static

# Bundle mock data so it's available without a volume mount (e.g. Railway)
COPY mock_data /data/mock

# Persistent DB lives here (mounted as a volume in compose)
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
