# Git 与 PR 记录

仓库：https://gitee.com/JinchengNie/fail-the-accounting-course 。个人分支 `czh`，目标 `master`。不强推、不修改组员提交历史，不自行合并公共分支。

| PR | 源 → 目标 | 状态（2026-11-17 核查） |
|---|---|---|
| !6 | review-audit → master | 已合并，合并提交 0c1d223 |
| !7 | review-ocr → review-audit | 已合并，合并提交 8e84eb6 |
| !8 | review-integration → review-ocr | 已合并，合并提交 5cee42f |
| !9 | review-reports → review-integration | 已合并，合并提交 9e5d03c |
| !10 | czh → master | 已合并，合并提交 5d59bad；不含后续完整项目 |
| [!11](https://gitee.com/JinchengNie/fail-the-accounting-course/pulls/11) | czh → master | 上次核查为开启、待审核；不自动合并 |

当前工作继续更新 !11，不再创建阶段分支。提交 `840e826` 保留 master 已合并的原始 README、OCR 脚本及测试；`9d7a7b9` 进行正式前后端/OCR/存储集成。后续提交补充文本导入、测试及报告。状态以 Gitee 页面实时结果为准。

## 审计结论与后续计划（2026-11-17）

!6～!9 是历史堆叠 PR，目标分别为前一阶段分支；!10 面向 master。其内容已有合并记录，不能再次包装为新的独立 PR。!11 包含完整应用、报告、真实 OCR 工作流和测试，继续将必要修复推送到 czh 更新该 PR。由于既有六个 PR 已达到参考范围，且本项目要求仅使用 czh 开发，不为数量创建重复 PR。剩余工作包括评审、学校在线表格同步、干净环境安装及其他 OCR 环境验证。

下表统计基线 `757fede` 之后 czh 的非合并提交；!11 列的变更在该 PR 审核时共同呈现，并不声称独立 PR。列出的结果是相关验证，不代表逐个历史提交均执行了所有测试。

| SHA | 功能或提交 | 所属 PR | 验证情况 |
|---|---|---|---|
| `206d258` | fix: load all menu pages in the review interface | !11 待审核 | 2001 条浏览器及完整 OCR 流程通过 |
| `5267c18` | fix: export and retrieve all matching menu records | !11 待审核 | 2001 条分页及导出测试通过 |
| `81350d8` | feat: support paginated dish queries and filtered totals | !11 待审核 | 2001 条分页及导出测试通过 |
| `ce83338` | feat: restore duplicate merge and image review controls | !11 待审核 | 参见 reports 测试证据 |
| `de51fc5` | style: tidy browser test formatting | !11 待审核 | 相关报告或人工核查 |
| `eec2ec7` | test: verify full menu workflow and update acceptance reports | !11 待审核 | 参见 reports 测试证据 |
| `9d7a7b9` | feat: integrate OCR workflow with server-backed menu management | !11 待审核 | 参见 reports 测试证据 |
| `840e826` | fix: preserve merged original project files | !11 待审核 | 参见 reports 测试证据 |
| `cd09b58` | test: document isolated complete-project verification | !11 待审核 | 参见 reports 测试证据 |
| `6d9f1d8` | feat: add self-contained integrated project | !11 待审核 | 参见 reports 测试证据 |
| `628b576` | docs: record czh integration pull request | !10 已合并 | 相关报告或人工核查 |
| `1c8571c` | docs: clarify dependent PR review sequence | !10 已合并 | 相关报告或人工核查 |
| `d1e78d5` | docs: record open Gitee review requests | !10 已合并 | 相关报告或人工核查 |
| `bda1816` | docs: record report review branch | !10 已合并 | 相关报告或人工核查 |
| `a6729d7` | docs: record test evidence and review status | !9（并进入 !10） | 相关报告或人工核查 |
| `e9f9dd3` | test: exercise image OCR through HTTP and storage | !8（并进入 !10） | 参见 reports 测试证据 |
| `51fb751` | fix: restore Windows OCR adapter and document startup | !7（并进入 !10） | 参见 reports 测试证据 |
| `d062d93` | docs: audit repository and integration baseline | !6（并进入 !10） | 相关报告或人工核查 |

PR 链接以本文件上方表格为准：!6～!10 已合并，!11 审查及测试均为 0/2（页面核查时）；不推断后续审批状态。
