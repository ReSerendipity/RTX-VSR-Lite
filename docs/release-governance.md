# 发布 / 回滚 规范（RTX-VSR-Lite）

> **来源与权威**：公共条款见 `ReSerendipity/.github` 的 `REPOSITORY_GUIDELINES.md` §10（发布 / 分发统一规范）。
> 本文件按统一模板填写本仓特有项，不重写或抵触 §10 的公共条款。

---

## 0. 远端优先（根原则，不可改写）

发布链的构建、打包、扫描、上传、推送**全部在 GitHub Actions 远端完成**；本地只做三件事：改版本位、落 CHANGELOG、`git tag` + `git push`。本地不执行打包 / 镜像构建 / 发布上传。

## 1. 版本号规范

- 遵循 **SemVer** `MAJOR.MINOR.PATCH`；预发布用 `-alpha.N` / `-beta.N` / `-rc.N`。
- **唯一权威版本位**：`pyproject.toml` 的 `[project] version`（当前 `1.0.0`）。
- 必须同步的其它版本位：
  - `rtx_vsr/__init__.py` 的 `__version__`（当前 `"1.0.0"`）；
  - `CHANGELOG.md` 的 `[VERSION]` 节标题。
- 版本位漂移由 待定（负责人+触发条件） 钉住——目前无自动化版本一致性测试，发版前须人工核对上述三处一致。
- 自动化方式：手动 tag（人工）；本仓未使用 release-please。

## 2. CHANGELOG 管理

- 遵循 **Keep a Changelog**：`Added / Changed / Fixed / Deprecated / Removed / Security`。
- 每次合并 `main` 在 `[Unreleased]` 追加；type 映射 `feat→Added`、`fix→Fixed`、`refactor→Changed`。
- 发版时 `[Unreleased]` → `[VERSION] - YYYY-MM-DD`。

## 3. 发布流程（远端）

1. 确认 `[Unreleased]` 条目完整
2. 同步版本位（见 §1 清单）
3. 本地打 tag 并推送：`git tag v<X.Y.Z>` → `git push origin v<X.Y.Z>`
4. 远端凭 tag 触发 `.github/workflows/release.yml` 构建 wheel + sdist 并生成 `SHA256SUMS.txt`
5. 远端建 **draft Release** 并挂资产（wheel、sdist、SHA256SUMS.txt）→ 人工审核后 `published`
6. 盯到终态：`gh run list` 确认绿；红了当场修或 revert 止损

## 4. 分发产物与完整性

| 产物 | 构建位置 | 标签 / 命名 | 完整性手段 |
|---|---|---|---|
| Python wheel（`*.whl`）+ sdist（`*.tar.gz`） | **远端** | semver `vX.Y.Z` tag；不可变 | `SHA256SUMS.txt` |

- **产物判定依据**：本仓 `pyproject.toml` 配置了 setuptools 构建后端与 `rtx_vsr` 包发现规则，可通过 `python -m build` 产出 wheel 与 sdist，属合法可分发产物。核心运行时依赖 `nvvfx` 不在 PyPI 上（须从 NVIDIA VSR SDK 单独获取，详见 README「安装 nvvfx」），但这不影响 Python 包本身作为可分发构件——用户 `pip install` 后仍需另行安装 nvvfx，该限制已在 README 明确声明。
- 本仓**无容器镜像**（不涉及 ghcr.io、Trivy、provenance/sbom）。
- 本仓**无桌面安装包**（不涉及 Tauri ed25519 签名）。
- **不使用 GPG 分离签名**（2026-10-18 裁决）。
- **不引入 `latest` 标签**。

## 5. 回滚

- **判定**（满足任一即触发）：待定（负责人+触发条件）
- **执行**：`git revert <bad-commit>`（保历史、可再 forward）；不可变产物按上一版 tag 重推。
- **破坏性动作**：重指向 / 删除 tag、移动任何远端 ref → **须仓库所有者单独授权**。
- **回滚后验证**：`python -m unittest discover -s tests -v` 通过。

## 6. SLA / 错误预算

- 本仓为本地运行的开源 CLI 工具，无服务端可用性指标，SLA / 错误预算不适用。

## 7. 发布前检查清单

- [ ] 版本位全部同步（见 §1 清单：`pyproject.toml`、`rtx_vsr/__init__.py`、`CHANGELOG.md`）
- [ ] CHANGELOG `[Unreleased]` 已改版本 + 日期
- [ ] `python -m unittest discover -s tests -v` 通过
- [ ] `ruff check .` 全绿
- [ ] **本地未产出任何发布交付物**（全部远端构建）

---

## 差异点采集清单（本仓取值）

| 占位符 | 采集来源 | 本仓取值 |
|---|---|---|
| 版本位文件与字段 | `pyproject.toml` | `pyproject.toml` `[project] version`，当前 1.0.0 |
| 其它需同步版本位 | `grep -rn` 版本串 | `rtx_vsr/__init__.py` `__version__`；`CHANGELOG.md` `[VERSION]` 节标题 |
| 版本一致性校验入口 | `tests/**` | 无（待定） |
| 自动化方式 | `.github/workflows/` | 手动 tag（无 release-please） |
| 发布 workflow 文件名 | `.github/workflows/` | `.github/workflows/release.yml` |
| 产物形态与标签规则 | 构建 workflow | Python wheel + sdist；semver `vX.Y.Z` tag |
| 完整性手段 | Release 资产清单 | `SHA256SUMS.txt` |
| 回滚判定阈值 | 运行手册 / 监控 | 待定（负责人+触发条件） |
| 回滚后验证命令 | `tests/smoke` 等 | `python -m unittest discover -s tests -v` |
| 技术栈 | `pyproject.toml` | Python 3.10+，setuptools |
| 部署目标 | `deploy/` / Pages workflow | 无（本地 CLI，无远端部署） |

## 禁止事项

- 不得重写 §10 的公共条款（远端优先、tag 驱动、版本位一致、不可变标签、扫描阻断、无 GPG）。
- 不得引入 `latest` 作发布基线；不得保留或新建 GPG 签名流程。
- 不得留空占位符，不得编造阈值。
