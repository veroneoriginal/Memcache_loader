# source/writer.py

import logging

import memcache

from .config import (
    BATCH_SIZE,
    MEMCACHE_SOCKET_TIMEOUT,
    SENTINEL,
)


def writer_worker(
        memc_addr,
        queue,
        results,
        dry_run=False,
):
    """
    Поток-писатель: забирает (key, packed) из очереди,
    батчами пишет в memcache.

    Args:
        memc_addr: адрес memcache-инстанса (например '127.0.0.1:33013')
        queue: очередь с парами (key, packed)
        results: список, куда добавляется кортеж (processed, errors)
        dry_run: если True — только логирование, без реальной записи
    """
    processed = 0
    errors = 0

    memc = None
    if not dry_run:
        memc = memcache.Client(
            [memc_addr],
            socket_timeout=MEMCACHE_SOCKET_TIMEOUT,
        )

    batch = {}
    while True:
        item = queue.get()
        if item is SENTINEL:
            break

        key, packed = item
        if dry_run:
            logging.debug(f"{memc_addr} - {key} -> ...")
            processed += 1
            continue

        batch[key] = packed

        if len(batch) >= BATCH_SIZE:
            failed = _flush_batch(memc, memc_addr, batch)
            processed += len(batch) - failed
            errors += failed
            batch = {}

    # дописываем остатки
    if batch and not dry_run:
        failed = _flush_batch(memc, memc_addr, batch)
        processed += len(batch) - failed
        errors += failed

    results.append((processed, errors))


def _flush_batch(
        memc,
        memc_addr,
        batch,
):
    """
    Отправляет батч в memcache через set_multi.
    Возвращает количество ошибок.
    """
    try:
        failed_keys = memc.set_multi(batch)
        return len(failed_keys)
    except Exception as e:
        logging.exception(f"Ошибка записи в memc {memc_addr}: {e}")
        return len(batch)
