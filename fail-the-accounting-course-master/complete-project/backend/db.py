"""SQLite persistence for menu images, OCR output and dish records."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("MENU_DATA_DIR", BASE_DIR / "data")) / "menu.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path() -> Path:
    return Path(os.environ.get("MENU_DB_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS menu_images (
                id TEXT PRIMARY KEY,
                store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                original_name TEXT NOT NULL,
                ocr_status TEXT NOT NULL,
                ocr_engine TEXT,
                ocr_result TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dish_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
                image_id TEXT REFERENCES menu_images(id) ON DELETE CASCADE,
                dish_name TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                record_type TEXT NOT NULL DEFAULT 'dish',
                match_confidence REAL,
                ocr_confidence REAL,
                anomaly TEXT NOT NULL DEFAULT 'none',
                verify_status TEXT NOT NULL DEFAULT 'pending',
                is_duplicate_of INTEGER,
                bbox_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_dishes_store ON dish_records(store_id);
            CREATE INDEX IF NOT EXISTS idx_dishes_image ON dish_records(image_id);
            CREATE INDEX IF NOT EXISTS idx_dishes_name ON dish_records(dish_name);
            """
        )


def list_stores() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at FROM stores ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_store(store_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, created_at FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
    return dict(row) if row else None


def get_or_create_store(name: str) -> dict[str, Any]:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("门店名称不能为空")
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, created_at FROM stores WHERE name = ?", (cleaned,)
        ).fetchone()
        if row:
            return dict(row)
        created_at = now_iso()
        cursor = connection.execute(
            "INSERT INTO stores(name, created_at) VALUES (?, ?)",
            (cleaned, created_at),
        )
        return {
            "id": int(cursor.lastrowid),
            "name": cleaned,
            "created_at": created_at,
        }


def create_image(
    *,
    image_id: str,
    store_id: int,
    file_path: str,
    original_name: str,
    ocr_status: str = "pending",
) -> dict[str, Any]:
    created_at = now_iso()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO menu_images(
                id, store_id, file_path, original_name, ocr_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                store_id,
                file_path,
                original_name,
                ocr_status,
                created_at,
                created_at,
            ),
        )
    return get_image(image_id) or {}


def update_image_ocr(
    image_id: str,
    *,
    status: str,
    engine: str | None = None,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE menu_images
            SET ocr_status = ?, ocr_engine = ?, ocr_result = ?,
                error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                engine,
                json.dumps(result, ensure_ascii=False) if result is not None else None,
                error_message,
                now_iso(),
                image_id,
            ),
        )


def _serialize_dish(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    bbox_json = value.pop("bbox_json", None)
    value["bbox"] = json.loads(bbox_json) if bbox_json else None
    return value


def get_image(image_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT i.*, s.name AS store_name
            FROM menu_images i
            JOIN stores s ON s.id = i.store_id
            WHERE i.id = ?
            """,
            (image_id,),
        ).fetchone()
    if not row:
        return None
    value = dict(row)
    if value.get("ocr_result"):
        value["ocr_result"] = json.loads(value["ocr_result"])
    return value


def delete_image(image_id: str) -> dict[str, Any] | None:
    image = get_image(image_id)
    if not image:
        return None
    with connect() as connection:
        connection.execute("DELETE FROM menu_images WHERE id = ?", (image_id,))
    return image


def add_parsed_records(
    store_id: int,
    image_id: str | None,
    records: list[dict[str, Any]],
    *, ocr_engine: str | None = None, ocr_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    created_at = now_iso()
    inserted_ids: list[int] = []
    with connect() as connection:
        for record in records:
            cursor = connection.execute(
                """
                INSERT INTO dish_records(
                    store_id, image_id, dish_name, price, category, record_type,
                    match_confidence, ocr_confidence, anomaly, verify_status,
                    bbox_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    store_id,
                    image_id,
                    record.get("dish_name", ""),
                    record.get("price", ""),
                    record.get("category", ""),
                    record.get("record_type", "dish"),
                    record.get("match_confidence"),
                    record.get("ocr_confidence"),
                    record.get("anomaly", "none"),
                    record.get("verify_status", "pending"),
                    json.dumps(record.get("bbox"), ensure_ascii=False)
                    if record.get("bbox")
                    else None,
                    created_at,
                    created_at,
                ),
            )
            inserted_ids.append(int(cursor.lastrowid))
        if image_id is not None and ocr_result is not None:
            cursor = connection.execute(
                "UPDATE menu_images SET ocr_status='done', ocr_engine=?, ocr_result=?, error_message=NULL, updated_at=? WHERE id=? AND store_id=?",
                (ocr_engine, json.dumps(ocr_result, ensure_ascii=False), now_iso(), image_id, store_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("OCR 图片不存在或不属于该门店")
    return [get_dish(item_id) for item_id in inserted_ids if get_dish(item_id)]


def _dish_filters(*, store_id=None, category=None, query=None, include_headers=False, image_id=None):
    conditions: list[str] = []
    params: list[Any] = []
    if not include_headers:
        conditions.append("d.record_type = 'dish'")
    if store_id is not None:
        conditions.append("d.store_id = ?")
        params.append(store_id)
    if category:
        conditions.append("d.category = ?")
        params.append(category)
    if query:
        conditions.append("d.dish_name LIKE ?")
        params.append(f"%{query}%")
    if image_id is not None:
        conditions.append("d.image_id = ?")
        params.append(image_id)
    return (f"WHERE {' AND '.join(conditions)}" if conditions else ""), params


def count_dishes(**filters: Any) -> int:
    where, params = _dish_filters(**filters)
    with connect() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM dish_records d {where}", params).fetchone()[0]


def list_dishes(
    *,
    store_id: int | None = None,
    category: str | None = None,
    query: str | None = None,
    include_headers: bool = False,
    limit: int = 500,
    offset: int = 0,
    image_id: str | None = None,
) -> list[dict[str, Any]]:
    where, params = _dish_filters(store_id=store_id, category=category, query=query,
                                  include_headers=include_headers, image_id=image_id)
    params.extend((max(1, min(limit, 2000)), max(0, offset)))
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT d.*, s.name AS store_name, i.original_name AS image_name,
                   CASE WHEN i.file_path IS NOT NULL AND i.file_path != '' THEN 1 ELSE 0 END AS has_image
            FROM dish_records d
            JOIN stores s ON s.id = d.store_id
            LEFT JOIN menu_images i ON i.id = d.image_id
            {where}
            ORDER BY d.id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [_serialize_dish(row) for row in rows]


def iter_dishes(**filters: Any):
    """Stream one SQLite snapshot so concurrent writes cannot shift export pages."""
    where, params = _dish_filters(**filters)
    connection = connect()
    try:
        cursor = connection.execute(
            f"""SELECT d.*, s.name AS store_name, i.original_name AS image_name,
                       CASE WHEN i.file_path IS NOT NULL AND i.file_path != '' THEN 1 ELSE 0 END AS has_image
                FROM dish_records d JOIN stores s ON s.id = d.store_id
                LEFT JOIN menu_images i ON i.id = d.image_id
                {where} ORDER BY d.id DESC""", params,
        )
        for row in cursor:
            yield _serialize_dish(row)
    finally:
        connection.close()


def get_dish(dish_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT d.*, s.name AS store_name, i.original_name AS image_name
            FROM dish_records d
            JOIN stores s ON s.id = d.store_id
            LEFT JOIN menu_images i ON i.id = d.image_id
            WHERE d.id = ?
            """,
            (dish_id,),
        ).fetchone()
    return _serialize_dish(row) if row else None


def create_dish(data: dict[str, Any]) -> dict[str, Any]:
    store_id = int(data["store_id"])
    if not get_store(store_id):
        raise ValueError("门店不存在")
    image_id = data.get("image_id")
    if image_id and not get_image(str(image_id)):
        raise ValueError("图片不存在")
    created_at = now_iso()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO dish_records(
                store_id, image_id, dish_name, price, category, record_type,
                match_confidence, ocr_confidence, anomaly, verify_status,
                bbox_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                image_id,
                str(data.get("dish_name", "")).strip(),
                str(data.get("price", "")).strip(),
                str(data.get("category", "")).strip(),
                str(data.get("record_type", "dish")),
                data.get("match_confidence"),
                data.get("ocr_confidence"),
                str(data.get("anomaly", "none")),
                str(data.get("verify_status", "pending")),
                json.dumps(data.get("bbox"), ensure_ascii=False)
                if data.get("bbox")
                else None,
                created_at,
                created_at,
            ),
        )
        item_id = int(cursor.lastrowid)
    item = get_dish(item_id)
    assert item is not None
    return item


def update_dish(dish_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "dish_name",
        "price",
        "category",
        "record_type",
        "match_confidence",
        "ocr_confidence",
        "anomaly",
        "verify_status",
        "is_duplicate_of",
    }
    fields: list[str] = []
    values: list[Any] = []
    for key, value in data.items():
        if key in allowed:
            fields.append(f"{key} = ?")
            values.append(value)
    if not fields:
        return get_dish(dish_id)
    fields.append("updated_at = ?")
    values.extend([now_iso(), dish_id])
    with connect() as connection:
        cursor = connection.execute(
            f"UPDATE dish_records SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_dish(dish_id)


def delete_dish(dish_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM dish_records WHERE id = ?", (dish_id,))
    return cursor.rowcount > 0


def clear_test_data() -> None:
    """Remove all rows while keeping the schema; intended for self-tests."""

    with connect() as connection:
        connection.execute("DELETE FROM dish_records")
        connection.execute("DELETE FROM menu_images")
        connection.execute("DELETE FROM stores")
