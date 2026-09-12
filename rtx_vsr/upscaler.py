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
"""NVIDIA RTX Video Super Resolution 引擎封装。

本模块只负责"如何与 nvvfx SDK 打交道"，不涉及任何解码/编码逻辑，
因此可以独立于视频容器格式被复用。
"""

from __future__ import annotations

import contextlib
import importlib.util
import logging
import sys
from typing import Optional, Tuple

import numpy as np
import torch

logger = logging.getLogger(__name__)

#: RTX VSR 硬件管线要求输出宽高按此像素步长对齐，否则 SDK 可能拒绝加载。
PIXEL_GRID: int = 8

#: 本工具的质量档位名 -> nvvfx 中 QualityLevel 的候选成员名（按优先级尝试）。
#: 不同 SDK 版本对这些常量的命名并不一致，因此给出候选列表而非单一名字。
QUALITY_MEMBERS: dict = {
    "low": ("LOW", "QUALITY_LOW"),
    "medium": ("MEDIUM", "QUALITY_MEDIUM"),
    "high": ("HIGH", "QUALITY_HIGH"),
    "ultra": ("ULTRA", "MAX", "QUALITY_ULTRA"),
}


class VsrUnavailable(RuntimeError):
    """nvvfx SDK 缺失、版本不符或 GPU 不满足要求时抛出。"""


def snap_to_grid(value: float, grid: int = PIXEL_GRID) -> int:
    """把像素尺寸向下吸附到 ``grid`` 的整数倍上。

    选择向下取整而不是四舍五入，是为了保证输出分辨率绝不超出调用方实际
    请求的尺寸，避免产生意外的额外放大倍率或越界写入。

    Args:
        value: 期望的像素尺寸，允许为浮点数（例如按比例缩放后的结果）。
        grid: 对齐步长，默认 8 像素。

    Returns:
        不小于一个 ``grid``、且为 ``grid`` 整数倍的像素尺寸。
    """
    steps = max(1, int(value) // grid)
    return steps * grid


def is_sdk_present() -> bool:
    """探测当前环境能否导入 nvvfx，不触发真正的 import 副作用。

    这是 CLI ``--dry-run`` 的自检依据，因此必须做到"任何异常都只返回
    False"：半损坏的 SDK 安装（目录存在但缺 ``__init__``、命名空间包、
    已加载但 ``__spec__`` 为空）都可能让探测本身抛错，而自检函数抛栈会
    让用户看不到有用信息。
    """
    if "nvvfx" in sys.modules:
        return sys.modules["nvvfx"] is not None
    try:
        return importlib.util.find_spec("nvvfx") is not None
    except (ValueError, ImportError, AttributeError, TypeError):
        return False


class VideoSuperRes:
    """把 nvvfx 的会话式 API 包装成一个可复用的逐帧超分器。

    推荐用 ``with`` 管理生命周期，退出时会自动释放显存::

        with VideoSuperRes(quality="ultra", scale_factor=2.0) as sr:
            size = sr.target_size_for(src_w, src_h)
            sr.initialize(size)
            big = sr.process_frame(frame)

    若显式给出 ``output_width`` / ``output_height``，整段视频使用固定输出尺寸；
    否则可在打开输入之后用 :meth:`target_size_for` 依据源分辨率推导。
    """

    def __init__(
        self,
        quality: str = "ultra",
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
        gpu_id: int = 0,
        scale_factor: Optional[float] = None,
    ) -> None:
        if quality not in QUALITY_MEMBERS:
            raise ValueError(
                f"未知的质量档位 {quality!r}，可选：{', '.join(sorted(QUALITY_MEMBERS))}"
            )
        if scale_factor is not None and scale_factor <= 1.0:
            raise ValueError("scale_factor 必须大于 1.0，否则没有超分意义")

        self.quality = quality
        self.output_width = output_width
        self.output_height = output_height
        self.scale_factor = scale_factor
        self.device = torch.device(f"cuda:{gpu_id}")

        self._scope: Optional[contextlib.ExitStack] = None
        self._engine = None

    # -------------------------------------------------------------- 生命周期
    def __enter__(self) -> "VideoSuperRes":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def _resolve_quality(self, nvvfx):
        """从 SDK 的 QualityLevel 枚举中取出与档位名对应的常量。

        这里刻意不传裸整数：nvvfx 的构造函数期望枚举成员，部分版本收到整数
        会静默回落到默认档位，导致 --quality 参数看起来生效实则无效。
        """
        table = getattr(getattr(nvvfx, "effects", None), "QualityLevel", None)
        if table is None:
            raise VsrUnavailable(
                "当前 nvvfx 未暴露 effects.QualityLevel 枚举，无法设定质量档位；"
                "请升级 NVIDIA VSR SDK 后重试"
            )
        for member in QUALITY_MEMBERS[self.quality]:
            level = getattr(table, member, None)
            if level is not None:
                return level
        raise VsrUnavailable(
            f"nvvfx 的 QualityLevel 中找不到与 {self.quality!r} 对应的成员，"
            f"可用成员：{[n for n in dir(table) if n.isupper()]}"
        )

    def initialize(self, output_size: Tuple[int, int]) -> None:
        """加载超分引擎。

        Args:
            output_size: 已经对齐过的 ``(宽, 高)``。

        Raises:
            VsrUnavailable: SDK 未安装，或与当前 GPU/驱动不兼容。
            RuntimeError: 引擎已经完成初始化。
        """
        if self._engine is not None:
            raise RuntimeError("引擎已初始化，请勿重复调用 initialize()")
        if not is_sdk_present():
            raise VsrUnavailable(
                "未检测到 nvvfx。请先安装 NVIDIA VSR SDK（详见 README 的安装步骤）"
            )

        import nvvfx

        width, height = output_size
        # 用 ExitStack 接管 SDK 上下文：close() 时会自动携带异常信息退出，
        # 相比手工调用退出方法，异常路径下也不会漏掉清理。
        scope = contextlib.ExitStack()
        try:
            engine = scope.enter_context(nvvfx.VideoSuperRes(self._resolve_quality(nvvfx)))
        except Exception as exc:  # 加载失败时不留半开状态
            scope.close()
            raise VsrUnavailable(f"RTX VSR 引擎初始化失败：{exc}") from exc

        engine.output_width = width
        engine.output_height = height
        engine.load()

        self._scope = scope
        self._engine = engine
        logger.info(
            "RTX VSR 就绪 - 档位 %s，输出 %dx%d，%s",
            self.quality,
            width,
            height,
            self.device,
        )

    def close(self) -> None:
        """释放引擎占用的显存；重复调用是安全的。"""
        if self._scope is not None:
            self._scope.close()
            logger.info("RTX VSR 显存已释放")
        self._scope = None
        self._engine = None

    @property
    def is_ready(self) -> bool:
        """引擎是否已完成初始化、可直接喂帧。"""
        return self._engine is not None

    # ------------------------------------------------------------ 尺寸与像素
    def target_size_for(self, src_width: int, src_height: int) -> Tuple[int, int]:
        """推导这一路视频的输出尺寸（结果已按像素网格对齐）。

        优先级：显式宽高 > 放大倍率 > 维持源分辨率。
        """
        if self.output_width and self.output_height:
            want = (self.output_width, self.output_height)
        elif self.scale_factor:
            want = (src_width * self.scale_factor, src_height * self.scale_factor)
        else:
            return (src_width, src_height)
        return (snap_to_grid(want[0]), snap_to_grid(want[1]))

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """对单帧做超分。

        Args:
            frame: HWC 布局的 uint8 图像，通道顺序与 cv2 读取结果一致（BGR）。

        Returns:
            超分后的 HWC uint8 数组，通道顺序与输入保持一致。
        """
        if self._engine is None:
            raise RuntimeError("引擎尚未 initialize()，无法处理帧")

        planar = torch.from_numpy(frame).permute(2, 0, 1).contiguous().to(self.device)
        outcome = self._engine.run(planar)
        restored = torch.from_dlpack(outcome.image).permute(1, 2, 0).cpu()

        # 不同 SDK 版本可能返回归一化浮点或原始 uint8，这里统一回 uint8，
        # 以便 VideoWriter 直接写入。先 round 再转型，避免截断带来的半级亮度损失。
        if restored.is_floating_point():
            restored = restored.mul(255.0).clamp_(0.0, 255.0).round_()
        return restored.numpy().astype(np.uint8, copy=False)
