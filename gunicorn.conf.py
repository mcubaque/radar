"""Configuracion de gunicorn. Un solo worker: el estado de vuelos vive en memoria y lo comparten los hilos.

Cada espectador en vivo (SSE) ocupa un hilo, asi que WEB_THREADS marca el tope de espectadores simultaneos
(MAX_STREAMS, 150 por defecto, debe quedar por debajo para que el resto de la API siga respondiendo).
"""
import os

bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = 1
threads = int(os.getenv("WEB_THREADS", "200"))
keepalive = 75
graceful_timeout = 10
accesslog = "-"
