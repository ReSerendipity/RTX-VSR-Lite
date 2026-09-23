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
"""核心数值不变量的离线回归检查（不依赖 nvvfx SDK）。

覆盖四类无需 SDK 的纯逻辑：
1. ``snap_to_grid``      —— 输出尺寸向下吸附到 8 的倍数；
2. ``target_size_for``   —— 显式宽高 > 放大倍率 > 维持源分辨率；
3. ``_resolve_quality``  —— QUALITY_MEMBERS 候选成员按序命中、缺失时抛 VsrUnavailable；
4. ``VideoProcessor._iter_videos`` —— 按扩展名过滤、不递归、稳定排序。

运行方式（仓库根目录）::

    python -m unittest discover -s tests -v

torch / cv2 属于 requirements.txt 的运行时依赖，但为控制安装体积，本测试
仅在**本机未安装**时用标准库桩对象顶替模块级 import；已安装真实包时直接使用，
不做顶替。nvvfx 全程不被导入、``initialize()`` 全程不被调用，因此编辑
upscaler.py / video_processor.py 后无需 SDK 即可立即得到行为证据。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _stub_missing(module_name: str, stub: types.ModuleType) -> None:
    """真实包未安装时，用桩对象顶替，保证 import rtx_vsr 不崩且零新增第三方依赖。"""
    if importlib.util.find_spec(module_name) is None:
        sys.modules[module_name] = stub


# ---------------------------------------------------------------- torch 桩
_torch_stub = types.ModuleType("torch")


class _FakeDevice:
    """顶替 torch.device：只保留字符串表示，不触碰任何 CUDA 逻辑。"""

    def __init__(self, spec: str) -> None:
        self.spec = str(spec)

    def __repr__(self) -> str:
        return self.spec


_torch_stub.device = _FakeDevice
# upscaler.process_frame 仅在注解/运行期使用 torch，其余属性按需补桩。
_stub_missing("torch", _torch_stub)

# ------------------------------------------------------------------ cv2 桩
_cv2_stub = types.ModuleType("cv2")
_cv2_stub.CAP_PROP_FRAME_WIDTH = 3
_cv2_stub.CAP_PROP_FRAME_HEIGHT = 4
_cv2_stub.CAP_PROP_FRAME_COUNT = 7
_cv2_stub.CAP_PROP_FPS = 5
_cv2_stub.VideoWriter_fourcc = lambda *_args, **_kwargs: 0
_stub_missing("cv2", _cv2_stub)

# 此时模块级 import 已可安全完成；若失败，让异常直接冒泡（测试即报错）。
from rtx_vsr import DEFAULT_EXTENSIONS, VsrUnavailable, VideoProcessor, VideoSuperRes, snap_to_grid  # noqa: E402
from rtx_vsr.upscaler import PIXEL_GRID, QUALITY_MEMBERS  # noqa: E402


def _fake_nvvfx(members: dict) -> types.ModuleType:
    """构造仅含 effects.QualityLevel 的桩 nvvfx 模块。

    Args:
        members: ``{成员名: 值}``；值为 None 表示该成员不存在。
    """
    nvvfx = types.ModuleType("nvvfx_stub")
    effects = types.ModuleType("nvvfx_stub.effects")
    table = types.SimpleNamespace(**members)
    effects.QualityLevel = table
    nvvfx.effects = effects
    return nvvfx


class SnapToGridTests(unittest.TestCase):
    """不变量：输出尺寸必须向下对齐到 PIXEL_GRID 的整数倍。"""

    def test_snaps_down_to_multiple(self):
        self.assertEqual(snap_to_grid(1082), 1080)
        self.assertEqual(snap_to_grid(1087), 1080)
        self.assertEqual(snap_to_grid(1089), 1088)

    def test_exact_multiple_unchanged(self):
        self.assertEqual(snap_to_grid(1080), 1080)
        self.assertEqual(snap_to_grid(1920), 1920)

    def test_float_input_floors_before_snapping(self):
        self.assertEqual(snap_to_grid(2160.99), 2160)
        self.assertEqual(snap_to_grid(1087.5), 1080)

    def test_below_one_grid_clamps_to_one_grid(self):
        # 边界：小于一个步长时至少返回一个步长，绝不返回 0。
        self.assertEqual(snap_to_grid(0), PIXEL_GRID)
        self.assertEqual(snap_to_grid(3), PIXEL_GRID)
        self.assertEqual(snap_to_grid(-16), PIXEL_GRID)

    def test_custom_grid_step(self):
        self.assertEqual(snap_to_grid(100, grid=16), 96)
        self.assertEqual(snap_to_grid(64, grid=16), 64)

    def test_result_is_always_grid_multiple_and_never_exceeds(self):
        for value in (1, 7, 8, 9, 63, 64, 1000, 1081, 4097):
            snapped = snap_to_grid(value)
            self.assertEqual(snapped % PIXEL_GRID, 0, f"{value} 对齐后应为 8 的倍数")
            if value >= PIXEL_GRID:
                self.assertLessEqual(snapped, value, f"{value} 向下对齐不得超出原值")


class TargetSizeForTests(unittest.TestCase):
    """优先级：显式宽高 > scale_factor > 维持源分辨率。"""

    def test_explicit_size_wins_over_scale(self):
        sr = VideoSuperRes(quality="high", output_width=3840, output_height=2164, scale_factor=2.0)
        self.assertEqual(sr.target_size_for(1920, 1080), (3840, 2160))

    def test_explicit_size_snapped_to_grid(self):
        sr = VideoSuperRes(output_width=1927, output_height=1082)
        self.assertEqual(sr.target_size_for(640, 360), (1920, 1080))

    def test_scale_factor_applies_and_snaps(self):
        sr = VideoSuperRes(scale_factor=1.5)
        # 3840*1.5=5760（整倍）、2162*1.5=3243.0 -> 3240（向下）。
        self.assertEqual(sr.target_size_for(3840, 2162), (5760, 3240))

    def test_no_explicit_no_scale_keeps_source(self):
        sr = VideoSuperRes()
        # 边界：未给尺寸时原样返回，且不做对齐（源尺寸本身由解码器保证）。
        self.assertEqual(sr.target_size_for(1921, 1081), (1921, 1081))

    def test_partial_explicit_falls_back_to_scale(self):
        # 负例：只给宽度不算显式，回落到 scale_factor 分支。
        sr = VideoSuperRes(output_width=3840, scale_factor=2.0)
        self.assertEqual(sr.target_size_for(960, 540), (1920, 1080))

    def test_invalid_quality_and_scale_rejected(self):
        # 负例：未知档位 / scale_factor <= 1.0 必须在构造期报错。
        with self.assertRaises(ValueError):
            VideoSuperRes(quality="bogus")
        with self.assertRaises(ValueError):
            VideoSuperRes(scale_factor=1.0)


class ResolveQualityTests(unittest.TestCase):
    """QUALITY_MEMBERS 按声明顺序命中第一个可用成员；全部缺失抛 VsrUnavailable。"""

    def test_first_available_member_wins(self):
        sr = VideoSuperRes(quality="medium")
        nvvfx = _fake_nvvfx({"MEDIUM": "enum-medium", "QUALITY_MEDIUM": "enum-q-medium"})
        self.assertEqual(sr._resolve_quality(nvvfx), "enum-medium")

    def test_falls_back_to_next_candidate_member(self):
        sr = VideoSuperRes(quality="ultra")
        nvvfx = _fake_nvvfx(
            {"ULTRA": None, "MAX": None, "QUALITY_ULTRA": "enum-q-ultra"}
        )
        self.assertEqual(sr._resolve_quality(nvvfx), "enum-q-ultra")

    def test_all_members_missing_raises_vsr_unavailable(self):
        # 负例：枚举表存在但没有任何候选成员。
        sr = VideoSuperRes(quality="low")
        nvvfx = _fake_nvvfx({"HIGH": "enum-high"})
        with self.assertRaises(VsrUnavailable):
            sr._resolve_quality(nvvfx)

    def test_missing_quality_level_table_raises_vsr_unavailable(self):
        # 负例：SDK 未暴露 effects.QualityLevel。
        sr = VideoSuperRes(quality="high")
        broken = types.SimpleNamespace(effects=types.SimpleNamespace(QualityLevel=None))
        with self.assertRaises(VsrUnavailable):
            sr._resolve_quality(broken)
        with self.assertRaises(VsrUnavailable):
            sr._resolve_quality(types.SimpleNamespace())

    def test_quality_member_mapping_is_locked(self):
        # 档位映射契约：故意改动 QUALITY_MEMBERS（如调换 ultra 候选顺序）会使本条失败。
        self.assertEqual(
            QUALITY_MEMBERS,
            {
                "low": ("LOW", "QUALITY_LOW"),
                "medium": ("MEDIUM", "QUALITY_MEDIUM"),
                "high": ("HIGH", "QUALITY_HIGH"),
                "ultra": ("ULTRA", "MAX", "QUALITY_ULTRA"),
            },
        )


class IterVideosTests(unittest.TestCase):
    """批量目录扫描：按 DEFAULT_EXTENSIONS 过滤、不递归、排序稳定。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.processor = VideoProcessor(upscaler=None)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, *names: str) -> None:
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_filters_by_extension_case_insensitively(self):
        self._touch("a.mp4", "b.mkv", "c.AVI", "d.mov", "notes.txt", "cover.jpg")
        found = self.processor._iter_videos(self.root, DEFAULT_EXTENSIONS)
        self.assertEqual([p.name for p in found], ["a.mp4", "b.mkv", "c.AVI", "d.mov"])

    def test_does_not_recurse_into_subdirectories(self):
        # 负例：子目录里的视频不应被收进批次。
        self._touch("top.mp4", "nested/deep.mp4")
        found = self.processor._iter_videos(self.root, DEFAULT_EXTENSIONS)
        self.assertEqual([p.name for p in found], ["top.mp4"])

    def test_sorted_order_is_stable(self):
        self._touch("z.mkv", "a.mp4", "m.mov")
        found = self.processor._iter_videos(self.root, DEFAULT_EXTENSIONS)
        self.assertEqual([p.name for p in found], ["a.mp4", "m.mov", "z.mkv"])
        # 重复扫描结果一致（排序稳定）。
        again = self.processor._iter_videos(self.root, DEFAULT_EXTENSIONS)
        self.assertEqual(found, again)

    def test_custom_extensions_override_default(self):
        self._touch("clip.webm", "clip.mp4")
        found = self.processor._iter_videos(self.root, (".webm",))
        self.assertEqual([p.name for p in found], ["clip.webm"])

    def test_empty_folder_returns_empty_list(self):
        # 边界：目录存在但没有可处理的文件。
        self._touch("readme.md")
        self.assertEqual(self.processor._iter_videos(self.root, DEFAULT_EXTENSIONS), [])


class LazySdkImportTests(unittest.TestCase):
    """结构约束：import rtx_vsr 不得触碰 nvvfx，构造对象不得触发 initialize()。"""

    def test_rtx_vsr_import_does_not_pull_in_nvvfx(self):
        self.assertNotIn("nvvfx", sys.modules)

    def test_construction_does_not_initialize_engine(self):
        sr = VideoSuperRes(quality="ultra", scale_factor=2.0)
        self.assertFalse(sr.is_ready)
        self.assertNotIn("nvvfx", sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
