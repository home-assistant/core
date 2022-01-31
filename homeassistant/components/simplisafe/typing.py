"""Define typing helpers for SimpliSafe."""
from typing import Union

from simplipy.system.v2 import SystemV2
from simplipy.system.v3 import SystemV3

SystemType = Union[SystemV2, SystemV3]
