# source/memc_load.py

# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конкурентный загрузчик логов трекера мобильных приложений в memcache.

Архитектура:

- multiprocessing.Pool — параллельная обработка нескольких .tsv.gz файлов

- threading внутри каждого процесса:
4 потока-писателя (по одному на тип устройства)

- Главный поток процесса читает строки и распределяет их
в очереди по типу устройства

- Потоки-писатели забирают данные из очередей и пишут в memcache батчами

Файлы переименовываются (с точкой-префиксом) в хронологическом порядке
после обработки всех.
"""

import glob
import logging
import multiprocessing
import os
import sys
from optparse import OptionParser

from . import appsinstalled_pb2

from .config import NORMAL_ERR_RATE, WORKER_COUNT
from .processor import process_file


def dot_rename(path):
    """
    Переименовывает файл, добавляя точку в начало имени.

    Используется для пометки обработанных файлов.
    Например: sample.tsv.gz -> sample.tsv.gz
    """
    head, fn = os.path.split(path)
    os.rename(path, os.path.join(head, "." + fn))


def prototest():
    """
    Проверяет корректность сериализации/десериализации protobuf.

    Создаёт UserApps из тестовых данных, сериализует в bytes,
    десериализует обратно и сравнивает — должны совпадать.
    """
    sample = (
        "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23\n"
        "gaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"
    )
    for line in sample.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 5:
            continue
        dev_type, dev_id, lat, lon, raw_apps = parts
        apps = [int(a) for a in raw_apps.split(",") if a.strip().isdigit()]
        lat, lon = float(lat), float(lon)
        ua = appsinstalled_pb2.UserApps()
        ua.lat = lat
        ua.lon = lon
        ua.apps.extend(apps)
        packed = ua.SerializeToString()
        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert ua == unpacked
    logging.info("Протобуф-тест пройден.")


def main(options):
    """
    Главная функция: оркестрирует параллельную обработку файлов.

    1. Собирает файлы по паттерну и сортирует хронологически
    2. Запускает multiprocessing.Pool для параллельной обработки
    3. После завершения всех процессов — последовательно переименовывает файлы
    """
    device_memc = {
        "idfa": options.idfa,
        "gaid": options.gaid,
        "adid": options.adid,
        "dvid": options.dvid,
    }

    # собираем и сортируем файлы хронологически (по имени)
    fnames = sorted(glob.glob(options.pattern))
    if not fnames:
        logging.info("Нет файлов для обработки")
        return

    logging.info(f"Найдено {len(fnames)} файлов в обработке")

    args_list = [(fn, device_memc, options.dry) for fn in fnames]

    # параллельная обработка — все файлы обрабатываются одновременно
    workers = min(options.workers, len(fnames))
    with multiprocessing.Pool(processes=workers) as pool:
        results = pool.map(process_file, args_list)

    # pool.map ДОЖДЁТСЯ завершения всех процессов
    # и только потом — последовательное переименование в том же порядке
    for fn, processed, errors in results:
        if not processed:
            dot_rename(fn)
            continue

        err_rate = float(errors) / processed
        if err_rate < NORMAL_ERR_RATE:
            logging.info(f"Приемлемая доля ошибок ({err_rate:.4f}). "
                         f"Успешная загрузка: {fn}")
        else:
            logging.error(
                f"Высокая доля ошибок ({err_rate:.4f} > {NORMAL_ERR_RATE}). "
                f"Неудачная загрузка: {fn}"
            )
        dot_rename(fn)


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-t", "--test", action="store_true", default=False)
    op.add_option("-l", "--log", action="store", default=None)
    op.add_option("--dry", action="store_true", default=False)
    op.add_option(
        "--pattern",
        action="store",
        default="/data/appsinstalled/*.tsv.gz",
    )
    op.add_option("--idfa", action="store", default="127.0.0.1:33013")
    op.add_option("--gaid", action="store", default="127.0.0.1:33014")
    op.add_option("--adid", action="store", default="127.0.0.1:33015")
    op.add_option("--dvid", action="store", default="127.0.0.1:33016")
    op.add_option(
        "--workers",
        action="store",
        type="int",
        default=WORKER_COUNT,
        help="Количество рабочих процессов",
    )
    (opts, args) = op.parse_args()

    log_level = logging.DEBUG if opts.dry else logging.INFO
    logging.basicConfig(
        filename=opts.log,
        level=log_level,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )

    if opts.test:
        prototest()
        sys.exit(0)

    logging.info(f"Загрузчик запущен с параметрами: {opts}")
    try:
        main(opts)
    except Exception as e:
        logging.exception(f"Непредвиденная ошибка: {e}")
        sys.exit(1)
