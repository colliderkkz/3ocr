"""运行 OCR、API 与集成测试。"""
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "backend"))
sys.path.insert(0, str(root / "ocr"))
import test_backend
import test_integration
import test_ocr

loader = unittest.defaultTestLoader
suite = unittest.TestSuite([
    loader.loadTestsFromTestCase(test_backend.ApiTest),
    loader.loadTestsFromTestCase(test_ocr.MenuParserTest),
    loader.loadTestsFromTestCase(test_ocr.SampleOcrTest),
    # Run integration methods defined by this subclass without duplicating the
    # inherited API suite; new integration cases must not need manual listing.
    *(test_integration.ImageIntegrationTest(name)
      for name in loader.getTestCaseNames(test_integration.ImageIntegrationTest)
      if name in test_integration.ImageIntegrationTest.__dict__),
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
