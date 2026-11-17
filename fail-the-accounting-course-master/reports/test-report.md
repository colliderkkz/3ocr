# 正式集成测试记录

环境：Windows、Python 3.12、系统中文 OCR、无头 Microsoft Edge。记录日期：2026-11-17。

| 验收项 | 实际结果 |
|---|---|
| 启动 | `python start.py --port 28441`，浏览器连接真实服务 |
| 上传及 OCR | 真实 PNG 返回 4 条菜品，HTTP 201 |
| 外部文本 | 后端解析并入库，刷新可读取，不显示假原图 |
| 编辑及保存 | PUT 200，数据库查询和刷新均保留修改 |
| 手工新增 | 通过 POST 保存，刷新可读取 |
| 原图 | HTTP 图片可加载，旋转和缩放可操作 |
| 导出 | 实际下载 XLSX，检查工作表含修改后的名称和价格 |
| 删除 | DELETE 200，刷新及 API 查询确认删除 |
| 重复合并 | 同门店同名同价记录显示疑似重复，合并后保留一条 |
| 异常 | 无效图片 415；模拟 OCR 422 和保存 500 均显示失败，保存失败未展示为成功 |
| 独立项目 | 临时目录仅复制完整项目后，`python tests/run_tests.py` 8 项通过 |

证据：`evidence/formal-unit-tests.log`、`evidence/formal-isolated-tests.log`、`evidence/formal-e2e.log`、`evidence/formal-e2e-saved.png`、`evidence/formal-export-test.xlsx`。后两类故障响应在浏览器测试中模拟，OCR 正常识别、数据存储和导出均为真实服务。截图为实际页面。

跨平台、全新环境安装及大于 2000 条数据尚未验证。学校在线表格未同步。
