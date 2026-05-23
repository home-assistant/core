"""Root conftest - add HA Core tests to sys.path."""

import sys
from pathlib import Path

core_root = Path(__file__).parent / ".." / "core"
if core_root.exists() and str(core_root) not in sys.path:
    sys.path.insert(0, str(core_root))
