# 更新日志（Changelog）

本文件记录本项目的显著变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- 打包配置 `pyproject.toml`：项目元数据、运行时依赖与 `rtx-vsr` 控制台入口点。
- `ruff` / `mypy` 配置（`pyproject.toml`）与 `.pre-commit-config.yaml` 提交前检查；
  `requirements-dev.txt` 开发工具清单。
- 协作资产：`CONTRIBUTING.md`、本 `CHANGELOG.md`、PR 模板、Issue 模板与 Dependabot 配置。

### 变更
- `.gitignore` 增加 `.qoder/`，并停止跟踪 AI 工具链产物（`git rm --cached`，不改写历史）。
- `requirements.txt` 与 `pyproject.toml` 的依赖增加版本上限约束。

### 已知遗留
- `mypy` 在既有源码上仍有若干类型告警（未纳入本次改动范围，待后续单独处理）。

## [1.0.0] - 2026-09-12

### 新增
- 首次发布：基于 NVIDIA RTX Video Super Resolution（`nvvfx`）的独立视频超分 CLI，
  包含 `rtx_vsr` 包、`main.py` 入口、Apache-2.0 许可与第三方归属声明（`NOTICE`）。
