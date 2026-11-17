from __future__ import annotations

import io
import http.client
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import db
from server import create_server


BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
SAMPLE = BASE_DIR / "sample" / "external-ocr-result.json"


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            prefix="member2-api-test-",
            ignore_cleanup_errors=True,
        )
        self.previous_database = os.environ.get("MENU_DB_PATH")
        os.environ["MENU_DB_PATH"] = str(
            Path(self.temporary.name) / "member2-menu.db"
        )
        db.init_db()
        db.clear_test_data()
        self.server = create_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()
        if self.previous_database is None:
            os.environ.pop("MENU_DB_PATH", None)
        else:
            os.environ["MENU_DB_PATH"] = self.previous_database

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
    ) -> tuple[int, dict | str]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8")
            raise AssertionError(f"HTTP {error.code}: {body}") from error
        with response:
            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(body)
            return response.status, body

    def test_health_and_frontend(self) -> None:
        status, health = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")

        status, page = self.request("/")
        self.assertEqual(status, 200)
        if health["modules"]["frontend"]:
            self.assertIn("食单识别", page)
        else:
            self.assertIn("后端接口已启动", page)

    def test_invalid_request_framing_is_rejected(self) -> None:
        host, port = self.server.server_address
        for headers, expected in [
            ({"Content-Length": "-1"}, 400),
            ({"Content-Length": "abc"}, 400),
            ({"Content-Length": str(31 * 1024 * 1024)}, 413),
            ({"Transfer-Encoding": "chunked"}, 400),
        ]:
            connection = http.client.HTTPConnection(host, port, timeout=5)
            connection.putrequest("POST", "/api/stores")
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, expected)
            response.read()
            connection.close()

    def test_invalid_pagination_parameters_return_400(self) -> None:
        for query in ("limit=0", "limit=2001", "limit=abc", "offset=-1", "offset=9223372036854775808"):
            with self.subTest(query=query):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(self.base_url + "/api/dishes?" + query, timeout=5)
                self.assertEqual(raised.exception.code, 400)

    def test_ocr_records_roll_back_if_image_store_does_not_match(self) -> None:
        first = db.get_or_create_store('门店 A')
        second = db.get_or_create_store('门店 B')
        db.create_image(image_id='image-a', store_id=first['id'], file_path='', original_name='external')
        with self.assertRaisesRegex(ValueError, '不属于'):
            db.add_parsed_records(second['id'], 'image-a', [{'dish_name': '不应保存'}],
                                  ocr_engine='test', ocr_result={'items': []})
        self.assertEqual(db.count_dishes(), 0)
        self.assertEqual(db.get_image('image-a')['ocr_status'], 'pending')

    def test_export_iterator_has_stable_snapshot_during_insert(self) -> None:
        with db.connect() as connection:
            connection.execute('PRAGMA journal_mode=WAL')
        store = db.get_or_create_store('快照门店')
        db.create_dish({'store_id': store['id'], 'dish_name': '第一条'})
        db.create_dish({'store_id': store['id'], 'dish_name': '第二条'})
        records = db.iter_dishes()
        first = next(records)
        db.create_dish({'store_id': store['id'], 'dish_name': '并发新增'})
        result = [first, *records]
        self.assertEqual({r['dish_name'] for r in result}, {'第一条', '第二条'})
        self.assertEqual(db.count_dishes(), 3)

    def test_external_ocr_storage_and_crud(self) -> None:
        payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
        status, created = self.request(
            "/api/ocr/results",
            method="POST",
            payload=payload,
        )
        self.assertEqual(status, 201)
        self.assertGreaterEqual(len(created["records"]), 3)

        status, queried = self.request("/api/dishes?q=" + quote("宫保"))
        self.assertEqual(status, 200)
        self.assertEqual(queried["count"], 1)
        dish_id = queried["dishes"][0]["id"]

        status, updated = self.request(
            f"/api/dishes/{dish_id}",
            method="PUT",
            payload={"price": "42", "verify_status": "verified"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["dish"]["price"], "42")

        status, deleted = self.request(f"/api/dishes/{dish_id}", method="DELETE")
        self.assertEqual(status, 200)
        self.assertTrue(deleted["deleted"])

    def test_export_xlsx(self) -> None:
        payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
        self.request("/api/ocr/results", method="POST", payload=payload)

        request = urllib.request.Request(self.base_url + "/api/dishes/export")
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            self.assertEqual(response.status, 200)

        self.assertIn("spreadsheetml", content_type)
        self.assertTrue(body.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("菜品名称", sheet)
        self.assertIn("门店名称", sheet)

    def test_export_preserves_special_characters_as_valid_spreadsheet_xml(self) -> None:
        store = db.get_or_create_store('中文 & 门店')
        db.create_dish({'store_id': store['id'], 'dish_name': '菜 <&>\x01_x0041_ 末'})
        with urllib.request.urlopen(self.base_url + '/api/dishes/export', timeout=10) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                sheet = archive.read('xl/worksheets/sheet1.xml')
        root = ET.fromstring(sheet)
        text = ''.join(root.itertext())
        self.assertIn('菜 <&>_x0001__x005F_x0041_ 末', text)
        self.assertIn('中文 & 门店', text)

    def test_dish_pagination_and_filtered_total(self) -> None:
        store = db.get_or_create_store("分页测试门店")
        now = db.now_iso()
        with db.connect() as connection:
            connection.executemany(
                "INSERT INTO dish_records(store_id, dish_name, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ((store["id"], f"分页菜品{i}", "测试", now, now) for i in range(2001)),
            )
        _, first = self.request("/api/dishes?limit=2000&category=" + quote("测试"))
        _, second = self.request("/api/dishes?limit=2000&offset=2000&category=" + quote("测试"))
        self.assertEqual((first["total"], first["count"], second["count"]), (2001, 2000, 1))
        self.assertEqual(second["dishes"][0]["dish_name"], "分页菜品0")
        self.assertTrue(set(d["id"] for d in first["dishes"]).isdisjoint(d["id"] for d in second["dishes"]))
        with urllib.request.urlopen(self.base_url + "/api/dishes/export?category=" + quote("测试"), timeout=10) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("分页菜品0", sheet)
        self.assertIn("分页菜品2000", sheet)
        self.assertEqual(sheet.count("分页菜品"), 2001)


if __name__ == "__main__":
    unittest.main()
