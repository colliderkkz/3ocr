# Bug 与改进汇总

| 编号 | 问题 | 修复及复测 |
|---|---|---|
| BUG-001 | Windows OCR 脚本缺失 | 完整版本提供脚本，真实样例通过；master 原有脚本已保留 |
| BUG-002 | 非图片仅凭扩展名被接受 | 基线函数实测接受伪造 PNG；正式版返回 415，浏览器与接口复测通过 |
| BUG-003 | 保存失败仍显示未入库的本地修改 | 基线浏览器模拟 500 后复现；正式版保留编辑框、提示错误，刷新不出现假保存 |

具体复现及证据见 `bug-tracker.csv` / `.xlsx`、`evidence/bug-002-before.log`、`evidence/bug-003-before.log`、`evidence/formal-e2e.log`。学校在线表格尚未同步。
