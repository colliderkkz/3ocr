"""Convert OCR text boxes into menu records.

The parser is intentionally rule-based so its output is deterministic and can
be tested without an OCR engine. OCR engines only need to provide ``text``,
``confidence`` and an optional four-point ``bbox`` for each text line.
"""

from __future__ import annotations

import re
from typing import Any


CATEGORY_WORDS = {
    "凉菜",
    "冷盘",
    "前菜",
    "开胃菜",
    "热菜",
    "招牌热菜",
    "炒菜",
    "招牌菜",
    "特色菜",
    "汤品",
    "汤类",
    "羹汤",
    "汤羹小食",
    "主食",
    "面食",
    "米饭类",
    "面条",
    "面条类",
    "饮品",
    "酒水",
    "饮料",
    "甜点",
    "甜品",
    "点心",
    "小吃",
    "海鲜",
    "烧烤",
    "火锅",
    "套餐",
    "拼盘",
}

NOISE_WORDS = (
    "本菜单",
    "人民币",
    "图片识别",
    "扫码点餐",
    "联系电话",
    "营业时间",
)

PRICE_BODY = r"\d+(?:\.\d{1,2})?(?:\s*[-~～至]\s*\d+(?:\.\d{1,2})?)?"
PURE_PRICE_RE = re.compile(
    rf"^[¥￥]?\s*(?P<price>{PRICE_BODY})\s*(?:元)?$", re.IGNORECASE
)
INLINE_PRICE_RE = re.compile(
    rf"^(?P<name>.+?)(?:\s+|[¥￥])\s*[¥￥]?\s*"
    rf"(?P<price>{PRICE_BODY})\s*(?:元)?$",
    re.IGNORECASE,
)
LEADER_RE = re.compile(r"[.．·…_\-\s]{2,}$")
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def _box_metrics(item: dict[str, Any]) -> tuple[float, float, float, float]:
    box = item.get("bbox") or item.get("box") or []
    if isinstance(box, dict):
        x = float(box.get("x", 0))
        y = float(box.get("y", 0))
        w = float(box.get("width", 0))
        h = float(box.get("height", 0))
        return x, y, x + w, y + h
    if len(box) >= 4 and not isinstance(box[0], (list, tuple)):
        x, y, w, h = (float(value) for value in box[:4])
        return x, y, x + w, y + h
    points = [point for point in box if isinstance(point, (list, tuple)) and len(point) >= 2]
    if points:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return min(xs), min(ys), max(xs), max(ys)
    return 0.0, 0.0, 0.0, 0.0


def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
        text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
        if not text:
            continue
        x1, y1, x2, y2 = _box_metrics(item)
        confidence = item.get("confidence", item.get("score", 1.0))
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 1.0
        normalized.append(
            {
                "text": text,
                "confidence": confidence,
                "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "height": max(1.0, y2 - y1),
            }
        )
    return sorted(normalized, key=lambda item: (item["y1"], item["x1"]))


def _header_name(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"^【|】$", "", compact)
    return compact


def _is_header(text: str) -> bool:
    compact = _header_name(text)
    if compact in CATEGORY_WORDS:
        return True
    if compact.endswith(("系列", "菜单")) and compact[:-2] in CATEGORY_WORDS:
        return True
    return False


def _clean_name(value: str) -> str:
    value = re.sub(r"^[•·\-—*]+\s*", "", value)
    value = LEADER_RE.sub("", value)
    return value.strip(" \t:：")


def _price_value(price: str) -> float | None:
    first = re.search(r"\d+(?:\.\d+)?", price)
    return float(first.group(0)) if first else None


def _anomaly(record: dict[str, Any]) -> str:
    if not record["dish_name"]:
        return "name_missing"
    if not record["price"]:
        return "price_missing"
    amount = _price_value(record["price"])
    if amount is not None and (amount < 1 or amount > 9999):
        return "price_abnormal"
    if (
        (record.get("ocr_confidence") or 1) < 0.6
        or (record.get("match_confidence") or 1) < 0.7
    ):
        return "low_confidence"
    return "none"


def parse_menu(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return structured dish/header records from engine text boxes."""

    lines = _normalize_items(items)
    records: list[dict[str, Any]] = []
    category = ""
    seen_header = False
    has_header = any(_is_header(line["text"]) for line in lines)

    for index, line in enumerate(lines):
        text = line["text"]
        compact = re.sub(r"\s+", "", text)
        base = {
            "dish_name": "",
            "price": "",
            "category": category,
            "record_type": "dish",
            "match_confidence": 1.0,
            "ocr_confidence": line["confidence"],
            "bbox": line["bbox"],
            "sort_order": index,
        }

        if _is_header(text):
            header = _header_name(text)
            if header.endswith("系列"):
                header = header[:-2]
            category = header
            base.update(
                {
                    "dish_name": text,
                    "category": header,
                    "record_type": "category_header",
                    "match_confidence": 1.0,
                }
            )
            records.append(base)
            seen_header = True
            continue

        price_only = PURE_PRICE_RE.fullmatch(text)
        if price_only:
            price = re.sub(r"\s+", "", price_only.group("price"))
            previous = next(
                (record for record in reversed(records) if record["record_type"] == "dish"),
                None,
            )
            if previous and not previous["price"]:
                row_delta = abs(line["y1"] - (previous.get("_y1") or line["y1"]))
                if row_delta <= max(18.0, line["height"] * 1.8):
                    previous["price"] = price
                    previous["match_confidence"] = max(
                        0.6,
                        min(previous.get("match_confidence", 0.8), 0.9 - row_delta / 200),
                    )
                    previous["bbox"] = [
                        [
                            min(previous["bbox"][0][0], line["bbox"][0][0]),
                            min(previous["bbox"][0][1], line["bbox"][0][1]),
                        ],
                        [
                            max(previous["bbox"][1][0], line["bbox"][1][0]),
                            max(previous["bbox"][1][1], line["bbox"][1][1]),
                        ],
                    ]
                    continue
            base.update(
                {
                    "price": price,
                    "match_confidence": 0.4,
                    "_y1": line["y1"],
                }
            )
            records.append(base)
            continue

        if compact in {"时价", "市价"}:
            base.update({"price": compact, "_y1": line["y1"]})
            records.append(base)
            continue

        if any(noise in text for noise in NOISE_WORDS):
            continue

        inline = INLINE_PRICE_RE.fullmatch(text)
        if inline:
            name = _clean_name(inline.group("name"))
            price = re.sub(r"\s+", "", inline.group("price"))
            if name and (CJK_RE.search(name) or len(name) >= 2):
                base.update(
                    {
                        "dish_name": name,
                        "price": price,
                        "match_confidence": 1.0,
                        "_y1": line["y1"],
                    }
                )
                records.append(base)
                continue

        if CJK_RE.search(text) and len(compact) >= 2:
            base.update(
                {
                    "dish_name": _clean_name(text),
                    "match_confidence": 0.8,
                    "_y1": line["y1"],
                }
            )
            if has_header and not seen_header:
                base["record_type"] = "invalid"
                base["match_confidence"] = 1.0
            records.append(base)

    seen: dict[tuple[str, str], int] = {}
    for index, record in enumerate(records):
        if record["record_type"] != "dish":
            record["anomaly"] = "none"
            record.pop("_y1", None)
            continue
        anomaly = _anomaly(record)
        key = (
            record["dish_name"].strip().casefold(),
            record["price"].strip(),
        )
        if key[0] and key[1] and key in seen:
            anomaly = "duplicate"
            record["duplicate_of"] = seen[key]
        elif key[0] and key[1] and key not in seen:
            seen[key] = index + 1
        record["anomaly"] = anomaly
        record["verify_status"] = "pending"
        record.pop("_y1", None)

    return records


def structured_lines(records: list[dict[str, Any]]) -> list[str]:
    """Return compact text suitable for command-line display or logs."""

    return [
        "\t".join(
            [
                record.get("dish_name", ""),
                record.get("price", ""),
                record.get("category", ""),
            ]
        )
        for record in records
        if record.get("record_type") == "dish"
    ]
