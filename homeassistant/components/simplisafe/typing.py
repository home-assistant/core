"""Define typing helpers for SimpliSafe."""
from simplipy.system.v2 import SystemV2
from simplipy.system.v3 import SystemV3

SystemType = SystemV2 | SystemV3
