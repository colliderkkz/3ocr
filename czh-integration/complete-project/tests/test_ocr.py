from __future__ import annotations

import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path

from menu_parser import parse_menu
from ocr_engine import recognize_image, _windows_ocr_recognize


BASE_DIR = Path(__file__).resolve().parent.parent / "ocr"
SAMPLE = BASE_DIR / "sample" / "sample-menu.png"


class MenuParserTest(unittest.TestCase):
    def test_name_and_separate_price_are_merged(self) -> None:
        records = parse_menu(
            [
                {
                    "text": "热菜",
                    "confidence": 0.99,
                    "bbox": [[80, 80], [180, 80], [180, 120], [80, 120]],
                },
                {
                    "text": "宫保鸡丁",
                    "confidence": 0.98,
                    "bbox": [[80, 160], [240, 160], [240, 200], [80, 200]],
                },
                {
                    "text": "38 元",
                    "confidence": 0.97,
                    "bbox": [[760, 160], [860, 160], [860, 200], [760, 200]],
                },
            ]
        )
        dishes = [item for item in records if item["record_type"] == "dish"]
        self.assertEqual(dishes[0]["dish_name"], "宫保鸡丁")
        self.assertEqual(dishes[0]["price"], "38")
        self.assertEqual(dishes[0]["category"], "热菜")


class SampleOcrTest(unittest.TestCase):
    def test_windows_timeout_is_explained(self) -> None:
        with patch("ocr_engine.shutil.which", return_value="powershell"), patch(
            "ocr_engine.subprocess.run", side_effect=subprocess.TimeoutExpired("ocr", 90)
        ):
            with self.assertRaisesRegex(RuntimeError, "识别超时"):
                _windows_ocr_recognize(SAMPLE)

    def test_preprocess_failure_removes_temporary_directory(self) -> None:
        locations = []
        def fail_preprocessing(image, directory):
            locations.append(directory)
            raise RuntimeError("preprocess failed")
        with patch("ocr_engine.preprocess_image", side_effect=fail_preprocessing):
            with self.assertRaisesRegex(RuntimeError, "preprocess failed"):
                recognize_image(SAMPLE)
        self.assertTrue(locations)
        self.assertFalse(locations[0].exists())

    def test_sample_image_has_structured_dishes(self) -> None:
        result = recognize_image(SAMPLE, engine="auto", preprocess=True)
        records = parse_menu(result["items"])
        dishes = {
            (item["dish_name"], item["price"])
            for item in records
            if item["record_type"] == "dish"
        }
        self.assertIn(("宫保鸡丁", "38"), dishes)
        self.assertIn(("麻婆豆腐", "28"), dishes)
        self.assertIn(("水煮鱼", "68"), dishes)


if __name__ == "__main__":
    unittest.main()
