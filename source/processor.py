# source/processor.py

import gzip
import logging
import threading
from queue import Queue

from .config import BATCH_SIZE, SENTINEL
from .parser import (
    parse_apps_installed,
    serialize_apps_installed,
)
from .writer import writer_worker


def process_file(args):
    """
    Обрабатывает один .tsv.gz файл.

    Читает строки в главном потоке,
    раскидывает по очередям (по типу устройства),

    4 потока-писателя параллельно пишут в свои memcache-инстансы.

    Args:
        args: кортеж (filename, device_memc, dry_run)

    Returns:
        кортеж (filename, processed, errors)
    """
    fn, device_memc, dry_run = args

    logging.info(f"Обработка {fn}")

    # создаём очередь и поток-писатель для каждого типа устройства
    queues = {}
    threads = []
    results = []

    for dev_type, memc_addr in device_memc.items():
        q = Queue(maxsize=BATCH_SIZE * 10)
        queues[dev_type] = q
        thread_results = []
        results.append(thread_results)
        t = threading.Thread(
            target=writer_worker,
            args=(memc_addr, q, thread_results, dry_run),
        )
        t.daemon = True
        t.start()
        threads.append(t)

    # читаем файл и раскидываем по очередям
    parse_errors = 0
    try:
        with gzip.open(fn, mode="rt", encoding="utf-8") as fd:
            for line in fd:
                line = line.strip()
                if not line:
                    continue
                apps_installed = parse_apps_installed(line)
                if not apps_installed:
                    parse_errors += 1
                    continue
                q = queues.get(apps_installed.dev_type)
                if not q:
                    parse_errors += 1
                    logging.error(
                        f"Неизвестный тип устройства:{apps_installed.dev_type}"
                    )
                    continue
                key, packed = serialize_apps_installed(apps_installed)
                q.put((key, packed))
    except OSError as e:
        logging.exception(f"Ошибка открытия файла {fn}: {e}")
        return fn, 0, 0

    # останавливаем писателей
    for q in queues.values():
        q.put(SENTINEL)

    for t in threads:
        t.join()

    # собираем результаты
    total_processed = 0
    total_errors = parse_errors
    for thread_results in results:
        for processed, errors in thread_results:
            total_processed += processed
            total_errors += errors

    return fn, total_processed, total_errors
