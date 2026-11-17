# G06-T007-3：菜单上传与识别结果页面

本目录是组员 3 的独立前端交付物，包含图片上传、预览、OCR 请求、菜品列表展示、人工校验和 Excel 导出页面。

## 直接打开

双击 `index.html` 即可打开页面。后端未启动时仍可使用内置样例、粘贴 OCR 文本和本地演示；页面不会把上传图片伪造为识别结果。

## 与后端一起运行

保持三个目录同级，然后启动组员 2：

```powershell
Set-Location "..\组员2_后端接口"
python server.py
```

浏览器打开 `http://127.0.0.1:8000/`。后端会自动托管本目录的 `index.html`。

在新的“上传批次”页选择 JPG/PNG 图片后，页面会调用：

```text
POST /api/ocr/recognize
```

然后将接口返回的 `records` 显示为菜品名、价格、分类和状态列表。

## 可配置后端地址

通过浏览器控制台指定其他后端地址：

```javascript
window.MENU_API_BASE = "http://127.0.0.1:8000";
```

默认在 HTTP 页面下使用当前站点地址，直接打开 `index.html` 时使用 `http://127.0.0.1:8000`。

## 文件说明

| 文件 | 作用 |
|---|---|
| `index.html` | 页面结构和样式 |
| `app.js` | 上传、OCR 请求、结果展示、校验与导出 |
| `sample-menu.svg` | 内置演示样例 |
| `sample-menu.png` | 可上传的真实 OCR 测试图片 |
| `demo-preview.png` | 页面预览图 |

本目录不需要 Node.js，也没有构建步骤。

## 上传 Gitee

```powershell
git init -b main
git add .
git commit -m "feat: add menu upload and OCR result page"
git remote add origin https://gitee.com/你的用户名/你的仓库.git
git push -u origin main
```
