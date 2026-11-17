"""Command-line OCR demo for the standalone algorithm deliverable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from menu_parser import parse_menu, structured_lines
from ocr_engine import recognize_image


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_IMAGE = BASE_DIR / "sample" / "sample-menu.png"


def main() -> None:
    parser = argparse.ArgumentParser(description="菜单图片 OCR 演示")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--engine",
        choices=("auto", "rapidocr", "windows"),
        default="auto",
    )
    args = parser.parse_args()
    if not args.image.exists():
        raise SystemExit(f"图片不存在：{args.image}")

    result = recognize_image(args.image, engine=args.engine, preprocess=True)
    records = parse_menu(result["items"])
    lines = structured_lines(records)
    try:
        image_label = str(args.image.resolve().relative_to(BASE_DIR))
    except ValueError:
        image_label = str(args.image)
    payload = {
        "image": image_label,
        "engine": result["engine"],
        "language": result.get("language", ""),
        "raw_text": result["raw_text"],
        "items": result["items"],
        "structured_text": lines,
        "records": records,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"结果已写入：{args.output}")

    print(f"OCR 引擎：{result['engine']}")
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
