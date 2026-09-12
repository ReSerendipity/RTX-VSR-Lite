#!/usr/bin/env python
# Copyright 2026 ReSerendipity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""RTX_VSR-lite 命令行入口。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rtx_vsr import VideoProcessor, VideoSuperRes, VsrUnavailable, is_sdk_present

#: ``--scale`` 允许取值 -> 实际倍率。
SCALE_CHOICES = {"1.5x": 1.5, "2x": 2.0, "3x": 3.0, "4x": 4.0}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NVIDIA RTX 视频超分辨率工具（独立版，无需 ComfyUI）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", "-i", required=True, help="输入视频文件或文件夹")
    parser.add_argument("--output", "-o", required=True, help="输出视频文件或文件夹")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--scale",
        "-s",
        choices=sorted(SCALE_CHOICES, key=lambda s: SCALE_CHOICES[s]),
        help="按倍率放大（与 --width/--height 互斥）",
    )
    group.add_argument("--width", "-W", type=int, help="输出宽度（需与 --height 同时给出）")
    group.add_argument("--height", "-H", type=int, help="输出高度（需与 --width 同时给出）")
    parser.add_argument(
        "--quality",
        "-q",
        choices=["low", "medium", "high", "ultra"],
        default="ultra",
        help="超分质量档位",
    )
    parser.add_argument("--fps", type=float, help="覆盖输出帧率，默认沿用源视频")
    parser.add_argument("--gpu", "-g", type=int, default=0, help="CUDA 设备编号")
    parser.add_argument(
        "--dry-run", action="store_true", help="只检查环境与参数，不解码任何帧"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="输出调试级日志")
    return parser


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    src = Path(args.input)
    if not src.exists():
        logging.error("输入路径不存在：%s", src)
        return 2

    if bool(args.width) != bool(args.height):
        logging.error("--width 与 --height 必须同时提供")
        return 2

    if not is_sdk_present():
        logging.error(
            "未检测到 nvvfx，RTX VSR 无法工作。请参考 README「安装 nvvfx」一节获取 NVIDIA VSR SDK。"
        )
        return 3

    try:
        upscaler = VideoSuperRes(
            quality=args.quality,
            output_width=args.width,
            output_height=args.height,
            scale_factor=SCALE_CHOICES[args.scale] if args.scale else None,
            gpu_id=args.gpu,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return 2

    if args.dry_run:
        logging.info(
            "环境检查通过：档位=%s，目标尺寸=%s，GPU=cuda:%d，输入=%s",
            upscaler.quality,
            f"{upscaler.output_width}x{upscaler.output_height}"
            if upscaler.output_width
            else (f"{upscaler.scale_factor}x" if upscaler.scale_factor else "同源"),
            args.gpu,
            src,
        )
        return 0

    processor = VideoProcessor(upscaler)
    try:
        # 输入是目录则整批处理，否则按单文件处理
        if src.is_dir():
            processor.process_batch(str(src), args.output)
        else:
            processor.process_file(str(src), args.output, fps=args.fps)
    except VsrUnavailable as exc:
        logging.error("RTX VSR 不可用：%s", exc)
        return 4
    except RuntimeError as exc:
        logging.error("处理失败：%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
