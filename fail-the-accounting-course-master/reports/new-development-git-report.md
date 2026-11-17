# 本轮新增开发：基线与任务清单

基线记录时间：2026-11-17（Asia/Shanghai）。本地 HEAD、远程 czh：`17d0c24d1339e9160b3e3d1cdaba2394976cbad9`；远程 master：`5d59bad8240be87b821735187c7a005a561530e0`。开始时工作区干净，本地和远程 czh 一致。远程 SHA 与 PR 状态通过 Gitee API 只读核实；Git fetch 因网络 TLS 失败，未更新跟踪引用。

本轮前 PR 为 !1～!11；!2、!11 开启，其余合并。历史 czh 在 `757fede..17d0c24` 范围有 19 个提交，全部不计入本轮。!11 的目标为 master，仍需审查，本轮新分支以 !11 的 HEAD 为基础，后续 PR 堆叠，逐层比较，避免重复差异。

| 工作包 / PR 目标 | 现有问题及位置 | 预期修改与验收 | 估计提交 |
|---|---|---|---|
| 请求健壮性（目标 czh） | backend/server.py 请求体长度、图片签名及参数处理不完整 | 非法长度、无效参数得到明确 4xx，已有流程通过 | 2～4 |
| OCR 可靠性（依赖请求健壮性） | ocr/ocr_engine.py 异常与清理；backend/server.py 识别写入 | 引擎超时等可诊断、资源释放；真实 Windows OCR 和异常测试通过 | 2～4 |
| 数据一致性（依赖 OCR） | backend/db.py 分页、提交分步执行 | 明确事务边界和分页一致性，回归/并发测试通过 | 2～4 |
| 前端交互（依赖数据） | web/app.js 大列表、刷新竞争与反馈 | 避免旧请求覆盖，失败不显示成功，浏览器回归通过 | 2～4 |
| 导出与验收（依赖前端） | Excel XML 特殊字符、边界和文档 | 中文特殊字符导出可解析，端到端和独立运行测试，报告可追溯 | 3～5 |

估计数量仅为拆分参考，以实际发现和可审查价值为准。禁止空提交、伪造结果、修改原始模块或合并公共 master。

## 本轮已创建的 PR（2026-11-17 核查）

| PR | 功能及源 → 目标 | 新增 Commit | 状态 | 测试 |
|---|---|---|---|---|
| [!12](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/12) | 请求校验：czh-quality → czh | 3 | 待审核 | HTTP 请求体和分页边界；真实 OCR |
| [!13](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/13) | OCR 可靠性：czh-ocr-reliability → czh-quality | 2 | 待审核 | 真实 Windows OCR；模拟超时和预处理异常；无效引擎 HTTP |
| [!14](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/14) | 数据一致性：czh-data-consistency → czh-ocr-reliability | 2 | 待审核 | 事务回滚、真实 OCR 入库、并发插入快照、2001 条导出 |
| [!15](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/15) | 界面反馈：czh-frontend-ux → czh-data-consistency | 2 | 待审核 | 真实浏览器刷新竞争和完整业务流程；模拟读取失败 |
| [!16](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/16) | 导出字符：czh-export-integrity → czh-frontend-ux | 1 | 待审核 | XML 解析、中文与特殊字符、2001 条导出 |
| [!17](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/17) | 验收与报告：czh-final-acceptance → czh-export-integrity | 包含后续报告状态更新 | 待审核 | 17 项自动测试、独立虚拟环境、真实浏览器流程 |

审核建议先按 !11 → !12 → !13 → !14 → !15 → !16 → !17 理解依赖。注意目标分支是前一功能分支：若要沿现有目标将所有成果传回 czh，必须由获授权的组员从 !17 向 !12 逆序合并，并保留目标分支；随后由组员审核合并 !11 才进入 master。若 !11 已先合并，则最终 czh 的新增成果还需要新的 czh → master PR。也可由组员根据实际审核情况重新设定目标，但每次都应复查差异。任何阶段均不得自行绕过审批；功能分支之间的合并不等于进入 master。

## 本轮提交记录

| SHA | 提交与代码变化 | PR | 实际验证 |
|---|---|---|---|
| c8c4f3d | 建立基线和任务审计 | !12 | Git 与 Gitee API 只读核查 |
| 425329d | 拒绝非法请求体长度和传输编码 | !12 | 真实 HTTP 400/413 测试 |
| 926f357 | 验证分页参数边界 | !12 | 无效分页参数真实 HTTP 400 |
| 6082cfa | Windows OCR 超时提示及临时目录清理 | !13 | 真实样例 OCR；异常分支模拟 |
| 1623b03 | 创建记录前验证 OCR 引擎 | !13 | 真实 HTTP 400，不创建门店或文件 |
| c44e687 | OCR 结果与菜品事务 | !14 | 跨门店回滚、真实 OCR 入库 |
| c212d7e | 单一 SQLite 快照导出 | !14 | 并发插入和 2001 条导出 |
| 283d974 | 阻止旧刷新覆盖新数据 | !15 | 真实后端、延迟 HTTP 响应的浏览器竞争测试 |
| 25a96ac | 区分保存失败与读取失败 | !15 | 完整浏览器流程；读取 500 模拟后真实数据库复核 |
| 5575483 | Excel XML 控制字符转义 | !16 | 真实 HTTP 导出 XML 解析；中文及特殊字符 |
| 9b16c9c | 自动发现新的集成测试 | !17 | 默认测试包含新用例 |
| e1551d7 | 记录独立环境验收与协作依赖 | !17 | 17 项测试、真实浏览器流程、报告核对 |

截至提交 e1551d7：本轮 12 个提交；本轮新增 6 个 PR，均待审核、0 已合并。本次记录 PR !17 状态的后续文档提交可通过 `git log 17d0c24..czh-final-acceptance` 查看，避免自引用提交 SHA。历史基线：`757fede..17d0c24` 共 19 个提交；历史 !1～!11 共 11 个 PR（其中历史 !2 与 !11 开启）。提交和 PR 数量不相加充数。

## 验收与局限

Windows / Python 3.12：17 项测试通过。复制项目到新目录并新建无第三方包的虚拟环境，17 项测试通过；依赖同机已有 Windows 中文 OCR，并非另一台全新电脑。真实浏览器完成图片上传、Windows OCR、展示、编辑、保存、查询、刷新、删除与下载 Excel，截图和日志见 `evidence/new-development/`；OCR 422、保存及刷新 500 是模拟响应。2001 条测试覆盖分页与导出；导出快照已覆盖并发插入，前端跨分页在并发变更下仍不保证完整快照，多人并发编辑仍采用最后写入，重复合并不会转移图片来源。RapidOCR、跨系统和学校在线表仍待验证或同步。

截至 `aea9886`：本轮 13 个提交，6 个新增 PR（!12～!17），均待审核、0 个已合并。后续记录调整本身可用上述 Git 命令核查，避免提交自引用。
