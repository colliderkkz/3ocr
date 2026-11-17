"""Dependency-free HTTP API and static server for the menu OCR demo."""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import traceback
import uuid
import zipfile
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.sax.saxutils import escape as xml_escape

BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent
MEMBER1_DIR = PARENT_DIR / "ocr"
MEMBER3_DIR = PARENT_DIR / "web"
if MEMBER1_DIR.exists():
    sys.path.insert(0, str(MEMBER1_DIR))

import db

try:
    from menu_parser import parse_menu, structured_lines
    from ocr_engine import recognize_image
except ImportError:
    parse_menu = None
    recognize_image = None

    def structured_lines(records: list[dict[str, Any]]) -> list[str]:
        return [
            "\t".join(
                [
                    str(record.get("dish_name", "")),
                    str(record.get("price", "")),
                    str(record.get("category", "")),
                ]
            )
            for record in records
            if record.get("record_type") == "dish"
        ]


FRONTEND_DIR = MEMBER3_DIR if MEMBER3_DIR.exists() else None
BACKEND_HOME = BASE_DIR / "backend-home.html"
DATA_DIR = Path(os.environ.get("MENU_DATA_DIR", BASE_DIR / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
MAX_BODY_BYTES = 30 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _field_text(form: dict[str, dict[str, Any]], name: str, default: str = "") -> str:
    item = form.get(name)
    if not item:
        return default
    return item.get("data", b"").decode("utf-8", errors="replace").strip()


def _header_text(value: str) -> str:
    """Browser multipart headers are latin-1 bytes that often contain UTF-8 names."""

    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def _parse_multipart(content_type: str, body: bytes) -> dict[str, dict[str, Any]]:
    boundary_match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
    if not boundary_match:
        raise ApiError(HTTPStatus.BAD_REQUEST, "multipart 请求缺少 boundary")
    boundary = (boundary_match.group(1) or boundary_match.group(2)).strip().encode()
    form: dict[str, dict[str, Any]] = {}

    for raw_part in body.split(b"--" + boundary)[1:]:
        if raw_part.startswith(b"--"):
            break
        part = raw_part
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        header_bytes, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        header_text = header_bytes.decode("latin-1", errors="replace")
        disposition = re.search(
            r'Content-Disposition:\s*form-data;\s*name="([^"]+)"'
            r'(?:;\s*filename="([^"]*)")?',
            header_text,
            re.IGNORECASE,
        )
        if not disposition:
            continue
        name = disposition.group(1)
        filename = _header_text(disposition.group(2) or "")
        content_type_match = re.search(
            r"Content-Type:\s*([^\r\n]+)", header_text, re.IGNORECASE
        )
        form[name] = {
            "filename": filename or "",
            "content_type": (
                content_type_match.group(1).strip() if content_type_match else ""
            ),
            "data": content,
        }
    return form


def _image_extension(content: bytes, filename: str) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "仅支持 JPG 或 PNG 图片")


def _stored_image_path(value: str) -> Path:
    """仅访问上传目录；兼容旧数据库中的绝对路径。"""
    candidate = Path(value)
    path = candidate if candidate.is_absolute() else UPLOADS_DIR / candidate
    resolved = path.resolve()
    if not resolved.is_relative_to(UPLOADS_DIR.resolve()):
        raise ApiError(HTTPStatus.NOT_FOUND, "图片文件不存在")
    return resolved


class MenuRequestHandler(BaseHTTPRequestHandler):
    server_version = "MenuOCR/1.0"

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_bytes(
        self,
        status: int,
        content: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _send_json(self, status: int, payload: Any) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(status, content, "application/json; charset=utf-8")

    def _body_length(self) -> int:
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "不支持 Transfer-Encoding 请求体")
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
            raise ApiError(HTTPStatus.BAD_REQUEST, "Content-Length 必须是非负整数")
        length = int(values[0])
        if length == 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "请求体不能为空")
        if length > MAX_BODY_BYTES:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "请求体超过 30 MB")
        return length

    def _read_json(self) -> dict[str, Any]:
        length = self._body_length()
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, f"JSON 格式错误：{error}") from error
        if not isinstance(value, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON 请求体必须是对象")
        return value

    def _read_multipart(self) -> dict[str, dict[str, Any]]:
        length = self._body_length()
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "请使用 multipart/form-data")
        return _parse_multipart(content_type, self.rfile.read(length))

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api(parsed.path, parse_qs(parsed.query))
            else:
                self._serve_static(parsed.path)
        except ApiError as error:
            self._send_json(error.status, {"error": error.message})
        except (ValueError, KeyError, TypeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            traceback.print_exc()
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"服务器内部错误：{error}"},
            )

    def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        parts = [unquote(part) for part in path.strip("/").split("/") if part]

        if parts == ["api", "health"] and self.command in {"GET", "HEAD"}:
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "menu-ocr-demo",
                    "api_version": "1.0",
                    "database": str(db.db_path()),
                    "modules": {
                        "ocr_algorithm": MEMBER1_DIR.exists(),
                        "frontend": FRONTEND_DIR is not None,
                    },
                    "ocr_engines": {
                        "rapidocr": self._module_available("rapidocr_onnxruntime"),
                        "windows_ocr": os.name == "nt"
                        and bool(shutil.which("powershell.exe") or shutil.which("pwsh")),
                    },
                },
            )
            return

        if parts == ["api", "stores"]:
            if self.command in {"GET", "HEAD"}:
                self._send_json(HTTPStatus.OK, {"stores": db.list_stores()})
                return
            if self.command == "POST":
                body = self._read_json()
                name = str(body.get("name", "")).strip()
                if not name:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "门店名称不能为空")
                store = db.get_or_create_store(name)
                self._send_json(HTTPStatus.CREATED, {"store": store})
                return

        if parts == ["api", "dishes"]:
            if self.command in {"GET", "HEAD"}:
                store_value = self._query_one(query, "store_id")
                store_id = int(store_value) if store_value else None
                limit = int(self._query_one(query, "limit") or "500")
                if not 1 <= limit <= 2000:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "limit 必须在 1 到 2000 之间")
                offset = int(self._query_one(query, "offset") or "0")
                if not 0 <= offset <= 2**63 - 1:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "offset 超出有效范围")
                include_headers = (self._query_one(query, "include_headers") or "").lower() in {
                    "1",
                    "true",
                    "yes",
                }
                filters = dict(store_id=store_id, category=self._query_one(query, "category"),
                               query=self._query_one(query, "q"), include_headers=include_headers)
                dishes = db.list_dishes(**filters, limit=limit, offset=offset)
                self._send_json(HTTPStatus.OK, {"dishes": dishes, "count": len(dishes),
                                                "total": db.count_dishes(**filters), "offset": offset})
                return
            if self.command == "POST":
                body = self._read_json()
                if "store_id" not in body:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "store_id 为必填项")
                if not str(body.get("dish_name", "")).strip() and body.get(
                    "record_type", "dish"
                ) == "dish":
                    raise ApiError(HTTPStatus.BAD_REQUEST, "菜品名称不能为空")
                dish = db.create_dish(body)
                self._send_json(HTTPStatus.CREATED, {"dish": dish})
                return

        if parts == ["api", "dishes", "export"] and self.command in {"GET", "HEAD"}:
            self._export_dishes(query)
            return

        if len(parts) == 3 and parts[:2] == ["api", "dishes"]:
            dish_id = int(parts[2])
            if self.command in {"GET", "HEAD"}:
                dish = db.get_dish(dish_id)
                if not dish:
                    raise ApiError(HTTPStatus.NOT_FOUND, "菜品记录不存在")
                self._send_json(HTTPStatus.OK, {"dish": dish})
                return
            if self.command == "PUT":
                dish = db.update_dish(dish_id, self._read_json())
                if not dish:
                    raise ApiError(HTTPStatus.NOT_FOUND, "菜品记录不存在")
                self._send_json(HTTPStatus.OK, {"dish": dish})
                return
            if self.command == "DELETE":
                if not db.delete_dish(dish_id):
                    raise ApiError(HTTPStatus.NOT_FOUND, "菜品记录不存在")
                self._send_json(HTTPStatus.OK, {"deleted": True, "id": dish_id})
                return

        if parts == ["api", "ocr", "recognize"] and self.command == "POST":
            self._recognize_upload()
            return

        if parts == ["api", "ocr", "results"] and self.command == "POST":
            self._accept_external_ocr()
            return

        if len(parts) == 3 and parts[:2] == ["api", "ocr"]:
            if self.command in {"GET", "HEAD"}:
                image = db.get_image(parts[2])
                if not image:
                    raise ApiError(HTTPStatus.NOT_FOUND, "OCR 图片结果不存在")
                image["records"] = list(db.iter_dishes(include_headers=True, image_id=parts[2]))
                self._send_json(HTTPStatus.OK, {"image": image})
                return

        if len(parts) == 4 and parts[:2] == ["api", "images"] and parts[3] == "file":
            self._serve_uploaded_image(parts[2])
            return

        if len(parts) == 3 and parts[:2] == ["api", "images"]:
            image_id = parts[2]
            if self.command in {"GET", "HEAD"}:
                image = db.get_image(image_id)
                if not image:
                    raise ApiError(HTTPStatus.NOT_FOUND, "图片不存在")
                self._send_json(HTTPStatus.OK, {"image": image})
                return
            if self.command == "DELETE":
                image = db.delete_image(image_id)
                if not image:
                    raise ApiError(HTTPStatus.NOT_FOUND, "图片不存在")
                try:
                    _stored_image_path(image.get("file_path", "")).unlink(missing_ok=True)
                except (OSError, ValueError, ApiError):
                    pass
                self._send_json(HTTPStatus.OK, {"deleted": True, "id": image_id})
                return

        raise ApiError(HTTPStatus.NOT_FOUND, "接口不存在")

    @staticmethod
    def _module_available(name: str) -> bool:
        try:
            return __import__(name) is not None
        except ImportError:
            return False

    @staticmethod
    def _query_one(query: dict[str, list[str]], name: str) -> str | None:
        values = query.get(name)
        return values[0].strip() if values and values[0].strip() else None

    def _resolve_store(self, form: dict[str, dict[str, Any]]) -> dict[str, Any]:
        store_id_text = _field_text(form, "store_id")
        if store_id_text:
            store = db.get_store(int(store_id_text))
            if not store:
                raise ApiError(HTTPStatus.NOT_FOUND, "门店不存在")
            return store
        store_name = _field_text(form, "store_name")
        if not store_name:
            raise ApiError(HTTPStatus.BAD_REQUEST, "请提供 store_id 或 store_name")
        return db.get_or_create_store(store_name)

    def _recognize_upload(self) -> None:
        if recognize_image is None or parse_menu is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "OCR 模块不可用，请检查完整项目的 ocr 目录及依赖",
            )
        form = self._read_multipart()
        image_part = form.get("image")
        if not image_part or not image_part.get("filename"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "缺少 image 图片字段")
        content = image_part.get("data", b"")
        if not content:
            raise ApiError(HTTPStatus.BAD_REQUEST, "上传图片为空")
        extension = _image_extension(content, image_part["filename"])
        engine = (_field_text(form, "engine", "auto") or "auto").lower()
        if engine not in {"auto", "rapidocr", "rapid", "windows", "windows-ocr"}:
            raise ApiError(HTTPStatus.BAD_REQUEST, "不支持的 OCR 引擎")
        store = self._resolve_store(form)
        image_id = str(uuid.uuid4())
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        image_path = UPLOADS_DIR / f"{image_id}{extension}"
        image_path.write_bytes(content)
        db.create_image(
            image_id=image_id,
            store_id=int(store["id"]),
            file_path=image_path.name,
            original_name=image_part["filename"],
            ocr_status="processing",
        )

        try:
            preprocess = _field_text(form, "preprocess", "true").lower() not in {
                "0",
                "false",
                "no",
            }
            result = recognize_image(image_path, engine=engine, preprocess=preprocess)
            items = result.get("items", [])
            if not items:
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "OCR 未识别到文字，请检查图片清晰度")
            parsed = parse_menu(items)
            saved = db.add_parsed_records(
                int(store["id"]), image_id, parsed, ocr_engine=result.get("engine"),
                ocr_result=result | {"structured_text": structured_lines(parsed)},
            )
            self._send_json(
                HTTPStatus.CREATED,
                {
                    "image": db.get_image(image_id),
                    "store": store,
                    "engine": result.get("engine"),
                    "raw_text": result.get("raw_text", ""),
                    "ocr_items": items,
                    "structured_text": structured_lines(parsed),
                    "records": saved,
                },
            )
        except Exception as error:
            db.update_image_ocr(
                image_id,
                status="failed",
                error_message=str(error)[:2000],
            )
            if isinstance(error, ApiError):
                raise
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"OCR 识别失败：{error}") from error

    def _accept_external_ocr(self) -> None:
        body = self._read_json()
        store_id_value = body.get("store_id")
        if store_id_value is None:
            store_name = str(body.get("store_name", "")).strip()
            if not store_name:
                raise ApiError(HTTPStatus.BAD_REQUEST, "请提供 store_id 或 store_name")
            store = db.get_or_create_store(store_name)
        else:
            store = db.get_store(int(store_id_value))
            if not store:
                raise ApiError(HTTPStatus.NOT_FOUND, "门店不存在")

        image_id = str(body.get("image_id", "")).strip() or str(uuid.uuid4())
        if not db.get_image(image_id):
            db.create_image(
                image_id=image_id,
                store_id=int(store["id"]),
                file_path="",
                original_name=str(body.get("image_name", "external-ocr")),
                ocr_status="processing",
            )

        records = body.get("records")
        items = body.get("items")
        if items is None and isinstance(body.get("ocr_result"), dict):
            items = body["ocr_result"].get("items", [])
        if items is None and body.get("ocr_text"):
            items = [
                {
                    "text": line,
                    "confidence": body.get("confidence", 1.0),
                    "bbox": [
                        [0, index * 30],
                        [100, index * 30],
                        [100, index * 30 + 20],
                        [0, index * 30 + 20],
                    ],
                }
                for index, line in enumerate(str(body["ocr_text"]).splitlines())
                if line.strip()
            ]
        if not isinstance(items, list):
            if isinstance(records, list):
                items = []
            else:
                raise ApiError(HTTPStatus.BAD_REQUEST, "items 必须是数组")

        engine = str(body.get("engine", "external"))
        raw_text = str(body.get("raw_text", "")) or "\n".join(
            str(item.get("text", "")) for item in items if isinstance(item, dict)
        )
        result = {"engine": engine, "items": items, "raw_text": raw_text}
        if not isinstance(records, list):
            if parse_menu is None:
                raise ApiError(
                    HTTPStatus.BAD_REQUEST,
                    "单独运行后端时请在 records 中提交结构化 OCR 结果",
                )
            records = parse_menu(items)
        saved = db.add_parsed_records(
            int(store["id"]), image_id, records, ocr_engine=engine,
            ocr_result=result | {"structured_text": structured_lines(records)},
        )
        self._send_json(
            HTTPStatus.CREATED,
            {
                "image": db.get_image(image_id),
                "store": store,
                "raw_text": raw_text,
                "structured_text": structured_lines(records),
                "records": saved,
            },
        )

    @staticmethod
    def _column_letter(index: int) -> str:
        letters = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    @classmethod
    def _build_xlsx(cls, headers: list[str], rows: list[list[str]]) -> bytes:
        def cell_xml(row_idx: int, col_idx: int, value: str) -> str:
            ref = f"{cls._column_letter(col_idx)}{row_idx}"
            # SpreadsheetML uses _xNNNN_ escapes for XML-forbidden characters.
            # Escape literal sequences first so they are not decoded as control characters.
            value = re.sub(r"_x([0-9a-fA-F]{4})_", r"_x005F_x\1_", value)
            value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]",
                           lambda match: f"_x{ord(match.group()):04X}_", value)
            return (
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_escape(value)}</t></is></c>'
            )

        all_rows = [headers, *rows]
        row_xml: list[str] = []
        for row_idx, values in enumerate(all_rows, start=1):
            cells = "".join(
                cell_xml(row_idx, col_idx, str(value))
                for col_idx, value in enumerate(values)
            )
            row_xml.append(f'<row r="{row_idx}">{cells}</row>')
        last_col = cls._column_letter(max(0, len(headers) - 1))
        sheet = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(row_xml)}</sheetData>'
            f'<autoFilter ref="A1:{last_col}{len(all_rows)}"/>'
            '</worksheet>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        workbook = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="菜单菜品" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", rels)
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        return buffer.getvalue()

    def _export_dishes(self, query: dict[str, list[str]]) -> None:
        store_value = self._query_one(query, "store_id")
        store_id = int(store_value) if store_value else None
        dishes = db.iter_dishes(
            store_id=store_id,
            category=self._query_one(query, "category"),
            query=self._query_one(query, "q"),
            include_headers=False,
        )
        headers = ["菜品名称", "价格", "分类", "门店名称", "批次日期"]
        rows: list[list[str]] = []
        for dish in dishes:
            if dish.get("record_type") and dish["record_type"] != "dish":
                continue
            rows.append(
                [
                    dish.get("dish_name", "") or "",
                    dish.get("price", "") or "",
                    dish.get("category", "") or "",
                    dish.get("store_name", "") or "",
                    (dish.get("created_at") or "")[:10],
                ]
            )
        workbook_bytes = self._build_xlsx(headers, rows)
        store_name = ""
        if store_id is not None:
            store = db.get_store(store_id)
            store_name = store["name"] if store else ""
        stamp = datetime.now().strftime("%Y%m%d")
        base_name = f"菜单菜品_{store_name}_{stamp}" if store_name else f"菜单菜品_{stamp}"
        filename = f"{base_name}.xlsx"
        self._send_bytes(
            HTTPStatus.OK,
            workbook_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            {
                "Content-Disposition": (
                    f"attachment; filename=\"{quote(filename)}\"; "
                    f"filename*=UTF-8''{quote(filename)}"
                )
            },
        )

    def _serve_uploaded_image(self, image_id: str) -> None:
        image = db.get_image(image_id)
        if not image or not image.get("file_path"):
            raise ApiError(HTTPStatus.NOT_FOUND, "图片不存在")
        path = _stored_image_path(image["file_path"])
        if not path.exists():
            raise ApiError(HTTPStatus.NOT_FOUND, "图片文件不存在")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send_bytes(HTTPStatus.OK, path.read_bytes(), content_type)

    def _serve_static(self, request_path: str) -> None:
        if request_path == "/" and FRONTEND_DIR is None:
            self._send_bytes(
                HTTPStatus.OK,
                BACKEND_HOME.read_bytes(),
                "text/html; charset=utf-8",
            )
            return
        if FRONTEND_DIR is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "未找到同级目录“组员3_前端页面”")
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        target = (FRONTEND_DIR / unquote(relative)).resolve()
        if not target.is_relative_to(FRONTEND_DIR.resolve()) or not target.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "页面或静态文件不存在")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "image/svg+xml",
        }:
            content_type += "; charset=utf-8"
        self._send_bytes(HTTPStatus.OK, target.read_bytes(), content_type)

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} " + format_string % args)


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    db.init_db()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return ThreadingHTTPServer((host, port), MenuRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="菜单 OCR Demo 后端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"菜单 OCR Demo 已启动：http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
