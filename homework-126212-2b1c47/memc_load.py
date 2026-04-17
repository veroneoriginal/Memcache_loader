# homework-126212-2b1c47/memc_load.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import gzip
import sys
import glob
import logging
import collections
from optparse import OptionParser
# brew install protobuf
# protoc --python_out=. ./appsinstalled.proto
# pip install protobuf
import appsinstalled_pb2
# pip install python-memcached
import memcache

NORMAL_ERR_RATE = 0.01
AppsInstalled = collections.namedtuple("AppsInstalled", ["dev_type", "dev_id", "lat", "lon", "apps"])


def dot_rename(path):
    head, fn = os.path.split(path)
    # atomic in most cases
    os.rename(path, os.path.join(head, "." + fn))


def insert_appsinstalled(memc_addr, appsinstalled, dry_run=False):
    ua = appsinstalled_pb2.UserApps()
    ua.lat = appsinstalled.lat
    ua.lon = appsinstalled.lon
    key = f"{appsinstalled.dev_type}:{appsinstalled.dev_id}"
    ua.apps.extend(appsinstalled.apps)
    packed = ua.SerializeToString()
    # @TODO persistent connection
    # @TODO retry and timeouts!
    try:
        if dry_run:
            logging.debug(f"{memc_addr} - {key} -> {str(ua).replace(chr(10), ' ')}")
        else:
            memc = memcache.Client([memc_addr])
            memc.set(key, packed)
    except Exception as e:
        logging.exception(f"Cannot write to memc {memc_addr}: {e}")
        return False
    return True


def parse_appsinstalled(line):
    line_parts = line.strip().split("\t")
    if len(line_parts) < 5:
        return
    dev_type, dev_id, lat, lon, raw_apps = line_parts
    if not dev_type or not dev_id:
        return
    try:
        apps = [int(a.strip()) for a in raw_apps.split(",")]
    except ValueError:
        apps = [int(a.strip()) for a in raw_apps.split(",") if a.strip().isdigit()]
        logging.info(f"Not all user apps are digits: `{line}`")
    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        logging.info(f"Invalid geo coords: `{line}`")
        return
    return AppsInstalled(dev_type, dev_id, lat, lon, apps)


def main(options):
    device_memc = {
        "idfa": options.idfa,
        "gaid": options.gaid,
        "adid": options.adid,
        "dvid": options.dvid,
    }
    for fn in glob.iglob(options.pattern):
        processed = errors = 0
        logging.info(f'Processing {fn}')
        try:
            with gzip.open(fn, mode='rt', encoding='utf-8') as fd:
                for line in fd:
                    line = line.strip()
                    if not line:
                        continue
                    appsinstalled = parse_appsinstalled(line)
                    if not appsinstalled:
                        errors += 1
                        continue
                    memc_addr = device_memc.get(appsinstalled.dev_type)
                    if not memc_addr:
                        errors += 1
                        logging.error(f"Unknown device type: {appsinstalled.dev_type}")
                        continue
                    ok = insert_appsinstalled(memc_addr, appsinstalled, options.dry)
                    if ok:
                        processed += 1
                    else:
                        errors += 1
        except OSError as e:
            logging.exception(f"Error opening file {fn}: {e}")
            continue

        if not processed:
            dot_rename(fn)
            continue

        err_rate = float(errors) / processed
        if err_rate < NORMAL_ERR_RATE:
            logging.info(f"Acceptable error rate ({err_rate}). Successful load")
        else:
            logging.error(f"High error rate ({err_rate} > {NORMAL_ERR_RATE}). Failed load")
        dot_rename(fn)


def prototest():
    sample = """idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23
gaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"""
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


if __name__ == '__main__':
    op = OptionParser()
    op.add_option("-t", "--test", action="store_true", default=False)
    op.add_option("-l", "--log", action="store", default=None)
    op.add_option("--dry", action="store_true", default=False)
    op.add_option("--pattern", action="store", default="/data/appsinstalled/*.tsv.gz")
    op.add_option("--idfa", action="store", default="127.0.0.1:33013")
    op.add_option("--gaid", action="store", default="127.0.0.1:33014")
    op.add_option("--adid", action="store", default="127.0.0.1:33015")
    op.add_option("--dvid", action="store", default="127.0.0.1:33016")
    (opts, args) = op.parse_args()

    log_level = logging.DEBUG if opts.dry else logging.INFO
    logging.basicConfig(
        filename=opts.log,
        level=log_level,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S'
    )

    if opts.test:
        prototest()
        sys.exit(0)

    logging.info(f"Memc loader started with options: {opts}")
    try:
        main(opts)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(1)
