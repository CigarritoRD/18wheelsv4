FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && groupadd -g 10001 appuser && useradd -r -u 10001 -g appuser appuser && mkdir -p /data && chown appuser:appuser /data
COPY app ./app
COPY run.py admin.py docker_start.py ./
ENV EW_DATA_DIR=/data EW_HOST=0.0.0.0 PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER root
EXPOSE 8080
CMD ["python", "docker_start.py"]
