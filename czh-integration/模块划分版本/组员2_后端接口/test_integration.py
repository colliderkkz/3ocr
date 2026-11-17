"""真实图片经 HTTP、OCR、解析及数据库的集成测试。"""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

import db
import server
from test_backend import ApiTest


class ImageIntegrationTest(ApiTest):
    def setUp(self):
        super().setUp()
        self.previous_uploads = server.UPLOADS_DIR
        server.UPLOADS_DIR = Path(self.temporary.name) / "uploads"

    def tearDown(self):
        server.UPLOADS_DIR = self.previous_uploads
        super().tearDown()

    def test_upload_image_and_query_saved_dishes(self):
        image = (Path(__file__).resolve().parent.parent / "组员1_OCR识别" / "sample" / "sample-menu.png").read_bytes()
        boundary = "menu-integration-test-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="store_name"\r\n\r\n测试门店\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="menu.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode("utf-8") + image + f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request(self.base_url + "/api/ocr/recognize", data=body,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(request, timeout=90) as response:
            self.assertEqual(response.status, 201)
            result = json.load(response)
        self.assertTrue(any(row.get("dish_name") == "宫保鸡丁" for row in result["records"]))
        status, queried = self.request("/api/dishes")
        self.assertEqual(status, 200)
        self.assertTrue(any(row.get("dish_name") == "宫保鸡丁" for row in queried["dishes"]))


if __name__ == "__main__":
    unittest.main()
