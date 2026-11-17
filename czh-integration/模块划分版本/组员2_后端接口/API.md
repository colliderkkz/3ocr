# 菜单 OCR 后端接口说明

服务默认地址：`http://127.0.0.1:8000`。在本目录启动：

```powershell
python server.py
```

所有接口返回 UTF-8 JSON。上传图片仅支持 JPG/PNG，单次请求上限 30 MB。

## 快速验证

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/ocr/results" `
  -H "Content-Type: application/json" `
  --data-binary "@sample/external-ocr-result.json"

curl.exe "http://127.0.0.1:8000/api/dishes"
```

该接口接收算法模块给出的结构化 OCR 结果并写入 SQLite。三个提交目录同级时，还可以使用图片上传识别接口，直接调用组员 1 的 OCR 模块。

## 接口清单

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 服务、数据库和 OCR 引擎状态 |
| GET | `/api/stores` | 查询门店 |
| POST | `/api/stores` | 新增门店 |
| POST | `/api/ocr/recognize` | 拼接组员 1 后上传图片并自动 OCR、解析、入库 |
| POST | `/api/ocr/results` | 接收外部 OCR 结果并解析、入库 |
| GET | `/api/ocr/{image_id}` | 查询单张图片的原始 OCR 与菜品记录 |
| GET | `/api/dishes` | 查询菜品，支持 `store_id`、`category`、`q`、`limit` |
| GET | `/api/dishes/export` | 导出菜品 Excel（.xlsx），支持 `store_id`、`category`、`q` 筛选 |
| POST | `/api/dishes` | 新增菜品记录 |
| GET | `/api/dishes/{id}` | 查询单条菜品 |
| PUT | `/api/dishes/{id}` | 修改菜名、价格、分类、校验状态等 |
| DELETE | `/api/dishes/{id}` | 删除菜品 |
| GET | `/api/images/{id}` | 查询图片元数据 |
| DELETE | `/api/images/{id}` | 删除图片及其 OCR 菜品 |

## 自动 OCR

`POST /api/ocr/recognize` 使用 `multipart/form-data`。

| 字段 | 必填 | 说明 |
|---|---|---|
| `image` | 是 | JPG/PNG 文件 |
| `store_id` | 二选一 | 已有门店 ID |
| `store_name` | 二选一 | 门店名，不存在时自动创建 |
| `engine` | 否 | `auto`、`rapidocr`、`windows` |
| `preprocess` | 否 | 默认 `true`，执行灰度、对比度增强和倾斜校正 |

返回示例：

```json
{
  "image": {"id": "c2d4...", "ocr_status": "done"},
  "engine": "Windows.Media.Ocr",
  "raw_text": "宫保鸡丁 38 元",
  "structured_text": ["宫保鸡丁\t38\t招牌热菜"],
  "records": [
    {
      "id": 1,
      "dish_name": "宫保鸡丁",
      "price": "38",
      "category": "招牌热菜",
      "record_type": "dish",
      "ocr_confidence": 1.0,
      "match_confidence": 1.0,
      "anomaly": "none",
      "verify_status": "pending"
    }
  ]
}
```

## 接收外部 OCR 结果

算法模块或第三方 OCR 可以调用 `POST /api/ocr/results`：

```json
{
  "store_id": 1,
  "image_name": "菜单-01.jpg",
  "engine": "PaddleOCR",
  "items": [
    {
      "text": "招牌热菜",
      "confidence": 0.98,
      "bbox": [[80, 220], [250, 220], [250, 260], [80, 260]]
    },
    {
      "text": "宫保鸡丁 38元",
      "confidence": 0.96,
      "bbox": [[80, 300], [520, 300], [520, 340], [80, 340]]
    }
  ]
}
```

也可以直接传 `ocr_text`（每行一条文本），或传已经解析好的 `records`。

## 菜品增删改查

新增：

```json
POST /api/dishes
{
  "store_id": 1,
  "dish_name": "水煮鱼",
  "price": "68",
  "category": "热菜",
  "verify_status": "verified"
}
```

查询：

```text
GET /api/dishes?store_id=1&category=热菜&q=鱼
```

修改：

```json
PUT /api/dishes/1
{
  "price": "58",
  "verify_status": "verified"
}
```

删除：

```text
DELETE /api/dishes/1
```

## 导出 Excel

```text
GET /api/dishes/export?store_id=1&category=热菜&q=鱼
```

## 数据表

SQLite 默认文件为 `data/menu.db`，包含：

- `stores`：门店。
- `menu_images`：图片路径、OCR 状态、原始 OCR JSON。
- `dish_records`：菜名、价格、分类、置信度、异常和校验状态。

可通过环境变量 `MENU_DB_PATH` 指定其他数据库文件。
