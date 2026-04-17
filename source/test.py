import threading
from queue import Queue

from source.parser import (
    parse_apps_installed,
    serialize_apps_installed,
    AppsInstalled,
)
from source import appsinstalled_pb2
from source.writer import writer_worker
from source.config import SENTINEL


class TestParseAppsinstalled:
    """
    Тесты парсинга строк TSV.
    """

    def test_valid_line(self):
        """
        Корректная строка парсится во все поля AppsInstalled.
        """

        line = "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567"
        result = parse_apps_installed(line)
        assert result is not None
        assert result.dev_type == "idfa"
        assert result.dev_id == "1rfw452y52g2gq4g"
        assert result.lat == 55.55
        assert result.lon == 42.42
        assert result.apps == [1423, 43, 567]

    def test_empty_line(self):
        """
        Пустая строка возвращает None.
        """
        assert parse_apps_installed("") is None

    def test_short_line(self):
        """
        Строка с менее чем 5 полями возвращает None.
        """
        assert parse_apps_installed("idfa\tdevid\t55.55") is None

    def test_missing_dev_type(self):
        """
        Пустой dev_type возвращает None.
        """
        assert parse_apps_installed("\tdevid\t55.55\t42.42\t1,2,3") is None

    def test_missing_dev_id(self):
        """
        Пустой dev_id возвращает None.
        """
        assert parse_apps_installed("idfa\t\t55.55\t42.42\t1,2,3") is None

    def test_invalid_coords(self):
        """
        Нечисловые координаты возвращают None.
        """
        assert parse_apps_installed("idfa\tdev1\tabc\t42.42\t1,2,3") is None

    def test_non_digit_apps_filtered(self):
        """
        Нечисловые ID приложений отфильтровываются, остальные сохраняются.
        """
        line = "idfa\tdev1\t55.55\t42.42\t1,abc,3"
        result = parse_apps_installed(line)
        assert result is not None
        assert result.apps == [1, 3]


class TestSerializeAppsinstalled:
    """
    Тесты сериализации/десериализации protobuf.
    """

    def test_serialize_and_deserialize(self):
        """
        Данные сериализуются в protobuf и корректно десериализуются обратно.
        """

        app = AppsInstalled(
            dev_type="idfa",
            dev_id="test123",
            lat=55.55,
            lon=42.42,
            apps=[1, 2, 3],
        )
        key, packed = serialize_apps_installed(app)

        assert key == "idfa:test123"

        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert unpacked.lat == 55.55
        assert unpacked.lon == 42.42
        assert list(unpacked.apps) == [1, 2, 3]

    def test_empty_apps(self):
        """
        Пустой список приложений сериализуется без ошибок.
        """
        app = AppsInstalled("gaid", "dev1", 0.0, 0.0, [])
        key, packed = serialize_apps_installed(app)

        assert key == "gaid:dev1"

        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert list(unpacked.apps) == []


class TestWriterWorker:
    """
    Тесты потока-писателя в режиме dry-run.
    """

    def test_dry_run_counts(self):
        """
        В dry-run режиме все записи считаются обработанными, ошибок нет.
        """
        q = Queue()
        results = []

        q.put(("idfa:dev1", b"packed1"))
        q.put(("idfa:dev2", b"packed2"))
        q.put(("idfa:dev3", b"packed3"))
        q.put(SENTINEL)

        t = threading.Thread(
            target=writer_worker,
            args=("127.0.0.1:33013", q, results, True),
        )
        t.start()
        t.join()

        processed, errors = results[0]
        assert processed == 3
        assert errors == 0

    def test_empty_queue(self):
        """
        Пустая очередь — 0 обработанных, 0 ошибок.
        """
        q = Queue()
        results = []

        q.put(SENTINEL)

        t = threading.Thread(
            target=writer_worker,
            args=("127.0.0.1:33013", q, results, True),
        )
        t.start()
        t.join()

        processed, errors = results[0]
        assert processed == 0
        assert errors == 0
