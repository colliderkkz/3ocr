"""OCR engine adapters and basic image preprocessing."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent
WINDOWS_OCR_SCRIPT = BACKEND_DIR / "windows_ocr.ps1"


def _preprocess_with_opencv(source: Path, target: Path) -> Path:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return source

    data = np.fromfile(str(source), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return source

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    inv = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    lines = cv2.HoughLinesP(
        inv,
        rho=1,
        theta=np.pi / 180,
        threshold=max(40, int(image.shape[1] * 0.08)),
        minLineLength=max(80, int(image.shape[1] * 0.25)),
        maxLineGap=20,
    )
    angle = 0.0
    if lines is not None:
        angles: list[float] = []
        for line in lines[:, 0]:
            x1, y1, x2, y2 = (float(value) for value in line)
            if x2 == x1:
                continue
            current = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(current) <= 12:
                angles.append(current)
        if len(angles) >= 2:
            angle = float(np.median(angles))
    if abs(angle) >= 0.15:
        height, width = enhanced.shape
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        enhanced = cv2.warpAffine(
            enhanced,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
    height, width = enhanced.shape
    if width < 1400:
        scale = 1400 / width
        enhanced = cv2.resize(
            enhanced,
            (1400, round(height * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    ok, encoded = cv2.imencode(".png", enhanced)
    if not ok:
        return source
    encoded.tofile(str(target))
    return target


def preprocess_image(source: Path, work_dir: Path) -> Path:
    return _preprocess_with_opencv(source, work_dir / f"{source.stem}-preprocessed.png")


def _rapidocr_recognize(image_path: Path) -> dict[str, Any] | None:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None

    engine = RapidOCR()
    result, _ = engine(str(image_path))
    items: list[dict[str, Any]] = []
    for entry in result or []:
        if len(entry) < 3:
            continue
        box, text, confidence = entry[0], entry[1], entry[2]
        items.append(
            {
                "text": str(text),
                "confidence": float(confidence),
                "bbox": [
                    [float(point[0]), float(point[1])]
                    for point in box
                    if len(point) >= 2
                ],
            }
        )
    return {
        "engine": "RapidOCR",
        "language": "ch",
        "items": items,
        "raw_text": "\n".join(item["text"] for item in items),
    }


def _windows_ocr_recognize(image_path: Path) -> dict[str, Any]:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("未找到 PowerShell，无法调用 Windows OCR")
    if not WINDOWS_OCR_SCRIPT.exists():
        raise RuntimeError("Windows OCR 脚本缺失")

    with tempfile.TemporaryDirectory(prefix="menu-ocr-") as temporary:
        output_path = Path(temporary) / "windows-ocr.json"
        command = [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WINDOWS_OCR_SCRIPT),
            "-ImagePath",
            str(image_path),
            "-OutputPath",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"Windows OCR 调用失败：{detail[:600]}")
        if not output_path.exists():
            raise RuntimeError("Windows OCR 未生成结果文件")
        import json

        result = json.loads(output_path.read_text(encoding="utf-8-sig"))

    items = []
    for line in result.get("lines", []):
        words = line.get("words") or []
        bbox = line.get("bbox")
        if not bbox and words:
            x1 = min(float(word["x"]) for word in words)
            y1 = min(float(word["y"]) for word in words)
            x2 = max(float(word["x"]) + float(word["width"]) for word in words)
            y2 = max(float(word["y"]) + float(word["height"]) for word in words)
            bbox = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        if not line.get("text"):
            continue
        items.append(
            {
                "text": line["text"],
                "confidence": float(line.get("confidence", 1.0)),
                "bbox": bbox or [],
            }
        )
    return {
        "engine": result.get("engine", "Windows.Media.Ocr"),
        "language": result.get("language", ""),
        "items": items,
        "raw_text": "\n".join(item["text"] for item in items),
    }


def recognize_image(
    image_path: Path, *, engine: str = "auto", preprocess: bool = True
) -> dict[str, Any]:
    """Run OCR and return a normalized engine-independent result."""

    selected = engine.strip().lower()
    work_path = image_path
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if preprocess:
        temporary = tempfile.TemporaryDirectory(prefix="menu-preprocess-")
        work_path = preprocess_image(image_path, Path(temporary.name))

    try:
        if selected in {"auto", "rapidocr", "rapid"}:
            result = _rapidocr_recognize(work_path)
            if result is not None:
                return result
            if selected != "auto":
                raise RuntimeError(
                    "RapidOCR 未安装，请执行：python -m pip install -r "
                    "requirements-ocr.txt（在 OCR 模块目录下执行）"
                )

        if selected in {"auto", "windows", "windows-ocr"}:
            if os.name != "nt":
                raise RuntimeError("Windows OCR 仅能在 Windows 上运行")
            return _windows_ocr_recognize(work_path)

        raise RuntimeError(f"不支持的 OCR 引擎：{engine}")
    finally:
        if temporary is not None:
            temporary.cleanup()
