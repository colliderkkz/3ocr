# Git 与仓库审计

审计日期：2026-11-16（北京时间）。

- 用户指定的下载目录没有自己的 `.git`；Git 在其父目录发现了另一个指向 GitHub 的仓库，不能把该仓库当成小组 Gitee 仓库。
- 同级 `gitee-review` 的 origin 为 https://gitee.com/JinchengNie/fail-the-accounting-course.git，与下载目录的文件及仓库历史相符。它原来位于 `remove-duplicate-archive`，含未跟踪的 Python 缓存；未清理或切换该工作区。
- 通过 `git ls-remote --symref` 和 `git fetch` 验证远程可读。远程默认分支为 `master`，获取时为 `757fede`；另有 `lxw`、`njc`、`xl`。`origin/lxw` 包含尚未合并到 master 的提交，不能丢弃或覆盖。
- 下载目录与获取的 master 业务文件一致（忽略测试产生的缓存）。独立工作树 `czh-integration` 从 `origin/master` 创建本地 `czh`，不影响原目录。
- `git push --dry-run origin HEAD:refs/heads/czh` 返回可创建分支；模拟推送不保证实际推送或 PR 权限。
- 不直接提交或合并到公共 master，不强推、不删除组员分支。用户先要求只使用 `czh`，本次创建的三个阶段分支曾被删除；之后用户明确允许为审查建立阶段分支，因此从已有提交重建 `review-audit`、`review-ocr`、`review-integration`。完整开发成果保留在 `czh`。
