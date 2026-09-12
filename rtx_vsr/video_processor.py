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
"""基于 OpenCV 的解码 -> 超分 -> 编码 管道。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional, Tuple

import cv2

from .upscaler import VideoSuperRes

logger = logging.getLogger(__name__)

#: 批量模式下默认识别的容器格式。
DEFAULT_EXTENSIONS: Tuple[str, ...] = (".mp4", ".mkv", ".avi", ".mov")

#: 写盘时使用的编码器；mp4v 兼容性最好，若需更高画质可自行换 fourcc。
OUTPUT_FOURCC: str = "mp4v"


class VideoProcessor:
    """把 :class:`VideoSuperRes` 接到真实视频文件上的薄封装。

    引擎的输出尺寸在加载时就已固定，所以每个输入文件都会按自身的源分辨率
    重新推导一次输出尺寸，再走一遍初始化/释放的流程。
    """

    def __init__(self, upscaler: VideoSuperRes, progress_every: int = 50) -> None:
        self.upscaler = upscaler
        self.progress_every = max(1, progress_every)

    # ------------------------------------------------------------------ 内部
    def _probe(self, cap: "cv2.VideoCapture") -> Tuple[int, int, int, float]:
        """读取源视频的宽、高、总帧数与帧率。"""
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        return width, height, frames, fps

    def _iter_videos(self, folder: Path, extensions: Iterable[str]) -> list:
        wanted = {e.lower() for e in extensions}
        return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in wanted)

    # ---------------------------------------------------------------- 对外接口
    def process_file(
        self,
        input_path: str,
        output_path: str,
        fps: Optional[float] = None,
    ) -> Path:
        """超分单个视频文件。

        Args:
            input_path: 源视频路径。
            output_path: 输出路径，父目录会自动创建。
            fps: 覆盖输出帧率；不传则沿用源视频帧率。

        Returns:
            实际写出的文件路径。

        Raises:
            RuntimeError: 源文件无法打开，或没有任何可处理帧。
        """
        src = Path(input_path)
        dst = Path(output_path)
        dst.parent.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开输入视频：{src}")

        try:
            src_w, src_h, total, src_fps = self._probe(cap)
            out_fps = fps or src_fps
            out_w, out_h = self.upscaler.target_size_for(src_w, src_h)

            if (out_w, out_h) == (src_w, src_h):
                logger.warning(
                    "未指定 --scale 或 --width/--height，输出将保持源分辨率 %dx%d",
                    src_w,
                    src_h,
                )
            logger.info(
                "%s：%dx%d -> %dx%d，共 %s 帧",
                src.name,
                src_w,
                src_h,
                out_w,
                out_h,
                total if total > 0 else "未知",
            )

            writer = cv2.VideoWriter(
                str(dst), cv2.VideoWriter_fourcc(*OUTPUT_FOURCC), out_fps, (out_w, out_h)
            )
            if not writer.isOpened():
                raise RuntimeError(
                    f"无法创建输出文件（编码器不可用或路径非法）：{dst}"
                )

            self.upscaler.initialize((out_w, out_h))
            written = 0
            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    writer.write(self.upscaler.process_frame(frame))
                    written += 1
                    if written % self.progress_every == 0:
                        if total > 0:
                            logger.info(
                                "进度 %.1f%% (%d/%d)", written / total * 100, written, total
                            )
                        else:
                            logger.info("已处理 %d 帧", written)
            finally:
                cap.release()
                writer.release()
                self.upscaler.close()

            if written == 0:
                dst.unlink(missing_ok=True)
                raise RuntimeError(f"源视频未解出任何帧：{src}")

            logger.info("完成：%s（%d 帧）", dst, written)
            return dst
        finally:
            # VideoWriter 在部分 Windows 上需等文件句柄释放后才能安全删除半成品
            self.upscaler.close()

    def process_batch(
        self,
        input_dir: str,
        output_dir: str,
        extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    ) -> list:
        """超分一个目录下的所有视频（不递归）。

        单个文件失败不会中断整批任务，最终返回成功的文件列表。
        """
        folder = Path(input_dir)
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

        videos = self._iter_videos(folder, extensions)
        if not videos:
            logger.warning("目录中没有可处理的视频：%s", folder)
            return []

        logger.info("发现 %d 个待处理文件", len(videos))
        done = []
        for index, video in enumerate(videos, 1):
            logger.info("[%d/%d] %s", index, len(videos), video.name)
            out = target / f"upscaled_{video.stem}{video.suffix}"
            try:
                done.append(self.process_file(str(video), str(out)))
            except Exception as exc:
                logger.error("跳过 %s：%s", video.name, exc)
        logger.info("批量任务结束：成功 %d / %d", len(done), len(videos))
        return done
