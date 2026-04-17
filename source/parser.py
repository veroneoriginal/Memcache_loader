# source/parser.py

import collections
import logging

from . import appsinstalled_pb2

AppsInstalled = collections.namedtuple(
    "AppsInstalled",
    ["dev_type", "dev_id", "lat", "lon", "apps"],
)


def parse_apps_installed(line):
    """
    Парсит строку TSV в именованный кортеж AppsInstalled.

    Возвращает None если строка невалидна.
    """
    line_parts = line.strip().split("\t")
    if len(line_parts) < 5:
        return None

    dev_type, dev_id, lat, lon, raw_apps = line_parts
    if not dev_type or not dev_id:
        return None

    try:
        apps = [int(a.strip()) for a in raw_apps.split(",")]
    except ValueError:
        apps = [
            int(a.strip()) for a in raw_apps.split(",") if a.strip().isdigit()
        ]
        logging.info(f"Не все ID приложений являются числами: `{line}`")

    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        logging.info(f"Некорректные координаты: `{line}`")
        return None

    return AppsInstalled(dev_type, dev_id, lat, lon, apps)


def serialize_apps_installed(apps_installed):
    """
    Сериализует AppsInstalled в пару (key, packed_bytes) через protobuf.
    """
    ua = appsinstalled_pb2.UserApps()
    ua.lat = apps_installed.lat
    ua.lon = apps_installed.lon
    ua.apps.extend(apps_installed.apps)
    key = f"{apps_installed.dev_type}:{apps_installed.dev_id}"
    packed = ua.SerializeToString()
    return key, packed
