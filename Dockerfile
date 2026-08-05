# Image de base avec la stack géospatiale pré-installée (GDAL/GEOS/PROJ)
FROM python:3.11-slim

# Dépendances système pour geopandas/rasterio/GDAL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev libgeos-dev libproj-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_CONFIG=/usr/bin/gdal-config
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000 8501
CMD ["python", "main.py"]
