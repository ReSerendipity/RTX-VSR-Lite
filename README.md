# RTX_VSR-lite

利用 **NVIDIA RTX Video Super Resolution (VSR)** 对视频文件做超分辨率放大的独立命令行工具。

无需安装 ComfyUI，直接以 `nvvfx` SDK 为后端，把一段低分辨率视频逐帧放大并重新编码输出。

> ⚠️ **现实提醒**：本项目的核心后端 `nvvfx` 目前**不随 PyPI 分发**，需要从 NVIDIA VSR SDK 单独获取。
> 如果你装不上 `nvvfx`，本仓库的代码依然可以正常导入和阅读（会自动跳过引擎加载），但无法真正跑超分。
> 请先确认能拿到 SDK，再决定是否投入时间。

## 功能特性

- **RTX VSR 超分**：调用 NVIDIA 专用硬件管线做逐帧超分
- **四档质量**：`low` / `medium` / `high` / `ultra`，映射到 SDK 的 `QualityLevel` 枚举
- **两种尺寸指定方式**：按倍率（`--scale 2x`）或按绝对分辨率（`--width/--height`）
- **批量模式**：输入目录即自动批处理，单文件失败不中断整批
- **多卡支持**：`--gpu` 指定 CUDA 设备
- **dry-run 自检**：`--dry-run` 只校验环境与参数，不解码任何帧
- **独立实现**：不依赖 ComfyUI，不依赖任何 GPL 代码（详见[许可证](#许可证)）

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **仅 Windows 10 / 11**（`nvvfx` 未提供 Linux/macOS 版本） |
| GPU | NVIDIA GeForce RTX 20 系列及以上 |
| 显存 | 建议 6 GB 以上（超分过程显存占用较高） |
| 驱动 | NVIDIA 531.18 或更新 |
| Python | 3.10+ |

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/ReSerendipity/RTX_VSR-lite.git
cd RTX_VSR-lite
```

### 2. 安装 Python 依赖

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

也可以直接运行 `start.bat`，它会自动完成建虚拟环境、装依赖、打印用法三步。

若希望以开发模式安装，并直接使用控制台命令（等价于 `python main.py`）：

```bash
pip install -e .
rtx-vsr --input video.mp4 --output upscaled.mp4 --scale 2x
```

### 3. 安装 nvvfx（关键步骤）

`nvvfx` **不在 PyPI 上**，`pip install nvidia-vfx` 这类命令目前是无效的。请从 NVIDIA 官方渠道获取 VSR SDK：

- **NVIDIA NGC**：<https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vsr-sdk>
- 若你的环境已有 ComfyUI-KJNodes 且能正常使用 `nvidia_rtx_vsr`，说明本机已存在可用的 `nvvfx`，本工具可直接复用，无需额外安装。

装好后自检：

```bash
python -c "import nvvfx; print(nvvfx.__file__)"
```

### 4. 验证环境

```bash
python main.py --input some_video.mp4 --output out.mp4 --scale 2x --dry-run
```

输出 `环境检查通过` 即代表 SDK 已就位、参数解析正常。

## 使用方法

### 单个文件

```bash
python main.py --input video.mp4 --output upscaled.mp4 --scale 2x --quality ultra
```

### 指定绝对分辨率

```bash
python main.py -i input.mp4 -o output.mp4 -W 1920 -H 1080 -q high
```

### 批量处理整个目录

`--input` 传目录即进入批量模式，输出文件名自动加 `upscaled_` 前缀：

```bash
python main.py --input ./videos --output ./upscaled --quality high
```

### Python API

```python
from rtx_vsr import VideoProcessor, VideoSuperRes

upscaler = VideoSuperRes(quality="ultra", scale_factor=2.0, gpu_id=0)
VideoProcessor(upscaler).process_file("input.mp4", "output.mp4")
```

逐帧自定义处理时，用 `with` 管理显存生命周期：

```python
from rtx_vsr import VideoSuperRes

with VideoSuperRes(quality="high", output_width=1920, output_height=1080) as sr:
    sr.initialize((1920, 1080))
    big_frame = sr.process_frame(frame)   # frame: HWC uint8 ndarray
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i, --input` | 输入视频文件或文件夹（目录即批量模式） | 必填 |
| `-o, --output` | 输出视频文件或文件夹 | 必填 |
| `-s, --scale` | 放大倍率：`1.5x` / `2x` / `3x` / `4x`（与 `-W/-H` 互斥） | — |
| `-W, --width` | 输出宽度，需与 `--height` 同时给出 | — |
| `-H, --height` | 输出高度，需与 `--width` 同时给出 | — |
| `-q, --quality` | 质量档位：`low` / `medium` / `high` / `ultra` | `ultra` |
| `--fps` | 覆盖输出帧率 | 沿用源视频 |
| `-g, --gpu` | CUDA 设备编号 | `0` |
| `--dry-run` | 只检查环境与参数，不解码帧 | 关闭 |
| `-v, --verbose` | 输出调试级日志 | 关闭 |

## 目录结构

```
RTX_VSR-lite/
├── rtx_vsr/
│   ├── __init__.py          # 公开 API 导出
│   ├── upscaler.py          # nvvfx 引擎封装、尺寸对齐
│   └── video_processor.py   # OpenCV 解码 -> 超分 -> 编码管道
├── main.py                  # CLI 入口
├── pyproject.toml           # 打包元数据与 ruff/mypy 工具配置
├── requirements.txt         # PyPI 依赖（不含 nvvfx）
├── start.bat                # Windows 一键装环境
├── LICENSE                  # Apache-2.0 全文
└── NOTICE                   # 版权与第三方归属声明
```

## 性能参考

下表为同级别 RTX VSR 管线的**大致量级参考，未经本机实测**，实际吞吐受驱动版本、显存占用、编解码开销影响很大：

| 输入 | 输出 | 量级 |
|------|------|------|
| 480p | 1080p | 数十 FPS |
| 720p | 1080p | 十余至数十 FPS |
| 1080p | 4K | 个位数至十余 FPS |

## 注意事项

- **仅限 Windows**：`nvvfx` 未提供其他平台版本
- **输出尺寸会向下对齐到 8 的倍数**：例如请求 1082 高会得到 1080，以保证绝不超出请求尺寸
- **通道顺序**：内部沿用 OpenCV 的 BGR 约定，输出与输入一致，不会偏色
- **显存**：建议处理时关闭其他占用 GPU 的应用
- **编码**：输出使用 `mp4v` fourcc；若需要 H.265 等高压缩编码，请自行改 `OUTPUT_FOURCC` 或接 ffmpeg

## 常见问题

### Q：`nvvfx` 到底从哪里装？

A：NVIDIA 尚未把它发布到 PyPI，可选路径：

1. **复用已有环境**：如果本机 ComfyUI-KJNodes 的 `nvidia_rtx_vsr` 能正常用，说明 `nvvfx` 已在当前 Python 环境的搜索路径里，本工具直接可用。
2. **NVIDIA VSR SDK / NGC 容器**：从 NGC 获取（需要 Docker）。
3. **商业授权**：联系 NVIDIA。

### Q：怎么确认我的 GPU 支持 RTX VSR？

A：需要 GeForce RTX 20 系列及以上（如 2070、2080、3060、4060、5070 Ti），或 Tesla T4 / A10 / A100、Quadro RTX 系列。运行 `nvidia-smi` 查看型号。

### Q：装不上 `nvvfx`，能先看代码结构吗？

A：可以。`import rtx_vsr` 不会触发 `nvvfx` 导入（引擎是延迟加载的），只有真正调用 `initialize()` 时才会检查。`--dry-run` 会在缺 SDK 时给出清晰的退出码 `3` 而不是抛栈。

### Q：为什么 `--quality` 传了却没效果？

A：本工具会把档位名解析成 SDK 的 `QualityLevel` 枚举成员再传入，而不是裸整数——不同 SDK 版本枚举成员命名不一致，代码里 `QUALITY_MEMBERS` 给了候选列表，若你的版本命中不到会抛 `VsrUnavailable` 并列出可用成员，按提示补一个名字即可。

## 贡献

开发环境、测试与提交规范见 [CONTRIBUTING.md](CONTRIBUTING.md)，变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

Apache License 2.0（全文见 [LICENSE](LICENSE)）。

本项目代码为**独立实现**，仅通过公开 API 调用 NVIDIA `nvvfx` SDK，不包含、不衍生自任何 GPL 许可的代码。用 `with`/`ExitStack` 管理的引擎生命周期、按 8 向下对齐的尺寸策略、OpenCV 视频管道与 CLI 均为本仓库原创。

第三方归属与 SDK 关系说明见 [NOTICE](NOTICE)。

## 致谢

- [NVIDIA](https://www.nvidia.com/) 提供 RTX Video Super Resolution SDK
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)（GPL-3.0）——「在图像缩放流程中接入 nvvfx」这一**技术思路**的公开示范者；本项目未使用其任何代码

## 免责声明

本项目与 NVIDIA Corporation 无隶属、背书或赞助关系。NVIDIA、GeForce、RTX、CUDA 为 NVIDIA 在美国和/或其他国家/地区的商标或注册商标。
