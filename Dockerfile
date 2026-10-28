FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --system --create-home skymonitor && mkdir -p /app/data && chown -R skymonitor /app/data
USER skymonitor

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Un solo worker: el estado de vuelos vive en memoria y se comparte entre hilos (SSE usa un hilo por cliente).
CMD ["gunicorn", "run:app", "--worker-class", "gthread", "--workers", "1", "--threads", "64", \
     "--bind", "0.0.0.0:8000", "--keep-alive", "75", "--graceful-timeout", "10", "--access-logfile", "-"]
