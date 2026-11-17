# 食单识别：菜单 OCR 与管理

统一应用将菜单上传、真实 OCR、结构化解析、人工校验、SQLite 存储、查询、删除和 Excel 导出连接起来。`web/` 是单一正式界面；`backend/` 提供 HTTP API 和数据库；`ocr/` 提供 Windows OCR / RapidOCR 及菜单解析；`tests/` 存放自动测试。正式界面吸收原 Demo 的菜单校验与导出流程，不再使用演示菜品或浏览器本地存储伪装为服务器数据。

## 环境与启动

- Python 3.10 或更新版本，Windows 系统中文 OCR 已安装并可用；或安装 `ocr/requirements-ocr.txt` 提供 RapidOCR 和图像预处理依赖。
- Windows 可在本目录创建虚拟环境并安装可选 OCR 依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ocr/requirements-ocr.txt
```

- 从本目录启动：

```powershell
python start.py
```

访问 http://127.0.0.1:8000/。输入门店名称，上传 JPG 或 PNG 菜单；识别结果自动写入数据库。点击“编辑”修改后保存并标记已校验，可刷新或重新打开浏览器核验数据。也可粘贴外部 OCR 文本由后端解析、手工新增菜品、合并重复项、删除菜品、缩放或旋转查看原图和导出全部菜品 Excel。合并重复项会删除当前记录并保留另一条，不转移当前记录的图片关联；旋转和缩放仅用于查看。测试图片在 `ocr/sample/sample-menu.png`。

默认只监听本机，数据库及图片保存在 `backend/data/`。设置 `MENU_DATA_DIR` 可指定数据库和图片存储目录；也可使用 `MENU_DB_PATH` 单独指定数据库路径。`python start.py --help` 可查看地址及端口参数。上传不超过 30 MB，文件必须具有 JPG/PNG 格式标记。服务未提供用户认证，仅用于本地课程演示。

## 测试

```powershell
python tests/run_tests.py
```

测试包含真实样例 OCR、解析、HTTP CRUD、导出、图片上传入库以及无效图片和 OCR 失败场景。测试真实 OCR 需要可用引擎，非 Windows 需安装上述依赖。浏览器完整流程验证步骤与结果见仓库 `reports/`。

浏览器测试需单独安装 Playwright 和 Chromium：`python -m pip install playwright`、`python -m playwright install chromium`。先以独立的临时 `MENU_DATA_DIR` 启动 `python start.py --port 28435`，再在另一个终端、同一项目目录运行 `python tests/browser_e2e.py`。测试会创建和删除测试记录，请勿指向真实业务数据库。可通过 `MENU_TEST_PORT` 和 `MENU_BROWSER_PATH` 指定端口与浏览器路径；`MENU_EVIDENCE_DIR` 可指定测试产物目录。

## 常见问题

- 显示后端连接失败：确认在本目录执行了启动命令，且访问地址端口一致。
- OCR 不可用：检查 Windows 中文 OCR 语言功能，或安装 RapidOCR 依赖后重试。
- 识别无文字：换用更清晰的菜单图片；错误不会被显示为识别成功。
- 数据未保存：查看页面错误提示；保存操作只有后端返回成功才会关闭编辑框。

分页回归：安装 Playwright 后运行 `python tests/browser_pagination.py`，测试在临时数据库中建立 2001 条数据并通过真实浏览器验证加载、搜索及刷新。可用 `MENU_BROWSER_PATH` 指定浏览器。列表当前在浏览器中加载全部记录；大量数据可能影响性能，并发增删期间分页结果不保证快照一致性。

### 本轮可靠性与复测

Windows OCR 超时上限为 90 秒；预处理失败会清理临时文件。未知引擎在建立上传记录之前返回 400。`GET /api/dishes` 的 `limit` 为 1～2000，`offset` 为非负整数；导出使用 SQLite 单次查询快照。默认测试入口自动发现新增集成用例。

浏览器刷新竞争测试：`python tests/browser_refresh_race.py`；它创建临时数据库并启动本机服务，需要 Playwright 浏览器。该测试延迟一次真实 HTTP 响应，验证较旧结果不会覆盖新结果。

已在本机新建的不含第三方包的 Python 3.12 虚拟环境、独立项目副本上通过默认测试；仍依赖本机 Windows 中文 OCR 系统组件，不能等同于在另一台全新电脑或其他操作系统验证。
