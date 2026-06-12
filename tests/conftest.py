"""pytest 配置：确保本地 src 优先于 site-packages"""

import sys
from pathlib import Path

# 将项目子目录根加入 sys.path（优先于 site-packages src）
_project_root = Path(__file__).parent
_src_dir = _project_root / "src"

# 确保当前项目的 src/ 目录优先于 PYTHONPATH 中其他项目的 src/
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
elif sys.path.index(str(_src_dir)) > 0:
    sys.path.remove(str(_src_dir))
    sys.path.insert(0, str(_src_dir))

# 项目根目录也加入（用于 api 等顶层导入）
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))