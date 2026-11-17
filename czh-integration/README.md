# 餐饮菜单 OCR 识别与管理系统

上传菜单图片，识别并解析菜品、价格及分类，在页面中校验、编辑和导出。项目由组员 1 的 OCR 与解析、组员 2 的 Python HTTP/SQLite 接口、组员 3 的浏览器页面组成；`ocr-menu-demo` 是此前的前端原型。

## 环境与启动

- Python 3.10 或更新版本；Windows 10/11 使用系统 OCR 时需安装并启用中文 OCR 语言功能。也可在 OCR 模块目录执行 `python -m pip install -r requirements-ocr.txt` 安装 RapidOCR 和图像预处理依赖。
- 在项目根目录运行：

```powershell
python "模块划分版本/组员2_后端接口/server.py"
```

打开 http://127.0.0.1:8000/。后端会加载同级 OCR 模块并托管组员 3 页面，SQLite 默认保存在后端目录的数据目录。示例图片位于 `模块划分版本/组员3_前端页面/sample-menu.png`。支持 `python "模块划分版本/组员2_后端接口/server.py" --help` 查看选项。测试和演示数据不应作为生产数据。

## 测试

```powershell
Push-Location "模块划分版本/组员1_OCR识别"
python -m unittest -v test_ocr
Pop-Location
Push-Location "模块划分版本/组员2_后端接口"
python -m unittest -v test_backend
Pop-Location
```

真实 OCR 测试依赖可用的中文 OCR 引擎，机器环境不同可能需要安装语言包或 RapidOCR。更多接口说明见 `模块划分版本/组员2_后端接口/API.md`。

## 常见问题

- 图片识别失败：确认中文 OCR 功能可用，或安装 OCR 模块的依赖；检查后端控制台返回的具体错误。
- 端口占用：使用 `--port` 指定空闲端口，并用相同端口访问页面。
- 离线数据：页面也使用浏览器存储；网络不可用或同步失败时，不能假定本地操作已写入服务器。
- 页面字体需要联网获取 Google Fonts；不可用时浏览器使用备用字体。

项目审计和测试情况见 `docs/` 与 `reports/`。
