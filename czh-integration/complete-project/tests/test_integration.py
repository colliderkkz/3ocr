"""真实图片经 HTTP、OCR、解析及数据库的集成测试。"""
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path

import db
import server
import test_backend


class ImageIntegrationTest(test_backend.ApiTest):
    def setUp(self):
        super().setUp()
        self.previous_uploads = server.UPLOADS_DIR
        server.UPLOADS_DIR = Path(self.temporary.name) / "uploads"

    def tearDown(self):
        server.UPLOADS_DIR = self.previous_uploads
        super().tearDown()

    def test_upload_image_and_query_saved_dishes(self):
        image = (Path(__file__).resolve().parent.parent / "ocr" / "sample" / "sample-menu.png").read_bytes()
        boundary = "menu-integration-test-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="store_name"\r\n\r\n测试门店\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="menu.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode("utf-8") + image + f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request(self.base_url + "/api/ocr/recognize", data=body,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(request, timeout=90) as response:
            self.assertEqual(response.status, 201)
            result = json.load(response)
        self.assertFalse(Path(result["image"]["file_path"]).is_absolute())
        with urllib.request.urlopen(self.base_url + "/api/images/" + result["image"]["id"] + "/file", timeout=10) as response:
            self.assertEqual(response.read(), image)
        self.assertTrue(any(row.get("dish_name") == "宫保鸡丁" for row in result["records"]))
        status, queried = self.request("/api/dishes")
        self.assertEqual(status, 200)
        self.assertTrue(any(row.get("dish_name") == "宫保鸡丁" for row in queried["dishes"]))

    def test_invalid_image_is_rejected(self):
        boundary = "invalid-image-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="store_name"\r\n\r\n测试门店\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="fake.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode() + b'not an image' * 30 + f'\r\n--{boundary}--\r\n'.encode()
        req = urllib.request.Request(self.base_url + "/api/ocr/recognize", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(raised.exception.code, 415)
        self.assertIn("仅支持", json.load(raised.exception)["error"])

    def test_unknown_engine_does_not_create_store_or_upload(self):
        image = (Path(__file__).resolve().parent.parent / "ocr" / "sample" / "sample-menu.png").read_bytes()
        boundary = "bad-engine"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="store_name"\r\n\r\n新门店\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="engine"\r\n\r\nunknown\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="menu.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode('utf-8') + image + f'\r\n--{boundary}--\r\n'.encode()
        req = urllib.request.Request(self.base_url + '/api/ocr/recognize', data=body,
                                     headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(raised.exception.code, 400)
        self.assertEqual(db.list_stores(), [])
        self.assertFalse(server.UPLOADS_DIR.exists())

    def test_ocr_failure_is_reported(self):
        image = (Path(__file__).resolve().parent.parent / "ocr" / "sample" / "sample-menu.png").read_bytes()
        boundary = "ocr-error-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="store_name"\r\n\r\n测试门店\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="menu.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode("utf-8") + image + f'\r\n--{boundary}--\r\n'.encode()
        previous = server.recognize_image
        server.recognize_image = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("测试引擎失败"))
        try:
            req = urllib.request.Request(self.base_url + "/api/ocr/recognize", data=body,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(req, timeout=10)
            self.assertEqual(raised.exception.code, 422)
            self.assertIn("测试引擎失败", json.load(raised.exception)["error"])
        finally:
            server.recognize_image = previous


if __name__ == "__main__":
    unittest.main()
