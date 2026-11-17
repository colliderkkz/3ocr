# G06-T007-2：菜单数据存储与后端接口

本目录是组员 2 的独立后端交付物，包含 HTTP API、SQLite 数据表、外部 OCR 结果入库和菜品增删改查。

## 启动

```powershell
python server.py
```

默认地址：`http://127.0.0.1:8000`。

若同级存在 `组员3_前端页面`，根路径 `/` 会自动托管前端页面。若不存在，则显示一个后端状态页，接口仍可正常使用。

## 直接验证

使用目录内自带的模拟 OCR 结果：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/ocr/results" `
  -H "Content-Type: application/json" `
  --data-binary "@sample/external-ocr-result.json"
```

查询菜品：

```powershell
curl.exe "http://127.0.0.1:8000/api/dishes"
```

## 测试

```powershell
python -m unittest -v test_backend
```

测试覆盖接口状态、OCR 结果入库、查询、修改和删除。

## 接口

完整接口见 `API.md`，主要接口包括：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 后端状态 |
| POST | `/api/ocr/results` | 接收 OCR 结果并入库 |
| GET | `/api/dishes` | 查询菜品 |
| POST | `/api/dishes` | 新增菜品 |
| GET | `/api/dishes/{id}` | 查询单条 |
| PUT | `/api/dishes/{id}` | 修改菜品 |
| DELETE | `/api/dishes/{id}` | 删除菜品 |
| POST | `/api/ocr/recognize` | 拼接组员 1 后上传图片直接 OCR |

`/api/ocr/recognize` 会尝试加载同级目录 `组员1_OCR识别`。单独上传组员 2 的仓库时，外部 OCR 结果入库和 CRUD 功能不依赖组员 1。

## 数据

默认 SQLite 文件为 `data/menu.db`，已加入 `.gitignore`，不会把测试数据提交到 Gitee。

## 上传 Gitee

```powershell
git init -b main
git add .
git commit -m "feat: add menu storage and CRUD APIs"
git remote add origin https://gitee.com/你的用户名/你的仓库.git
git push -u origin main
```
