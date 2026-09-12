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
"""RTX_VSR-lite 公开 API。"""

from .upscaler import (
    PIXEL_GRID,
    VsrUnavailable,
    VideoSuperRes,
    is_sdk_present,
    snap_to_grid,
)
from .video_processor import DEFAULT_EXTENSIONS, VideoProcessor

__version__ = "1.0.0"

__all__ = [
    "VideoSuperRes",
    "VideoProcessor",
    "VsrUnavailable",
    "is_sdk_present",
    "snap_to_grid",
    "PIXEL_GRID",
    "DEFAULT_EXTENSIONS",
    "__version__",
]
