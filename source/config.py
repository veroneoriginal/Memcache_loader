# source/config.py
"""Константы и настройки загрузчика."""

import multiprocessing

NORMAL_ERR_RATE = 0.01
BATCH_SIZE = 500
SENTINEL = None  # сигнал остановки для потоков-писателей
MEMCACHE_SOCKET_TIMEOUT = 3
WORKER_COUNT = multiprocessing.cpu_count()
