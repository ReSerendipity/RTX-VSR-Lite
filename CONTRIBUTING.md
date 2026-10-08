# 贡献指南（Contributing）

感谢你愿意为 RTX_VSR-lite 做贡献。本文档说明本地开发、验证与提交方式。

## 环境准备

```bash
git clone https://github.com/ReSerendipity/RTX-VSR-Lite.git
cd RTX-VSR-Lite
python -m venv venv
venv\Scripts\activate                    # Windows；Linux/macOS 用 source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt      # 开发/提交前工具：ruff / mypy / pre-commit
```

> 提示：核心后端 `nvvfx` 不在 PyPI 上，需要从 NVIDIA VSR SDK 单独获取，详见 README
> 「安装 nvvfx」一节。缺少它时 `import rtx_vsr` 仍可正常工作，但无法真正执行超分。

## 运行测试

测试不依赖 `nvvfx`，可在任意平台离线运行：

```bash
python -m unittest discover -s tests -v
```

`torch` / `cv2` 未安装时，测试会自动使用标准库桩对象顶替其模块级 import，因此无需 GPU
即可验证纯逻辑。

## 静态检查

```bash
ruff check .            # lint（规则集见 pyproject.toml [tool.ruff.lint]）
ruff format --check .   # 格式
mypy                    # 类型检查（读取 pyproject.toml [tool.mypy] 配置）
```

按需把检查装成 git 钩子，提交前自动运行：

```bash
pre-commit install
```

## 提交规范

采用[约定式提交](https://www.conventionalcommits.org/zh-hans/)：

- `feat:` 新功能
- `fix:` 缺陷修复
- `docs:` 文档
- `refactor:` 重构（不含行为变化）
- `test:` 测试
- `build:` 构建 / 打包 / 依赖
- `ci:` CI 配置
- `chore:` 杂项维护

提交信息建议写明**动机**与**受影响文件**。请保持提交原子化，一次提交对应一件事。

## 提交 Pull Request

1. 从 `main` 新建分支：`git checkout -b feat/your-change`
2. 完成改动，并确保 `python -m unittest discover -s tests` 通过、`ruff check .` 无告警
3. 按仓库的 PR 模板填写说明
4. 目标分支为 `main`

## 范围与边界

- 本仓库为**独立实现**，仅通过公开 API 调用 NVIDIA `nvvfx` SDK，请勿引入 GPL 许可代码
  （参见 [`NOTICE`](NOTICE)）。
- 请勿提交本地工具链产物（如 `.qoder/`）或视频处理产物，相关路径已在 `.gitignore` 中忽略。

## 许可证

贡献即表示同意你的代码以本项目所使用的 Apache-2.0 许可发布。
