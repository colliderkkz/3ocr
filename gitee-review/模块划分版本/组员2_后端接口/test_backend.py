from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import db
from server import create_server


BASE_DIR = Path(__file__).resolve().parent
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


if __name__ == "__main__":
    unittest.main()
