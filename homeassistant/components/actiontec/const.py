"""Support for Actiontec MI424WR (Verizon FIOS) routers."""
from __future__ import annotations

import re
from typing import Final

LEASES_REGEX: Final[re.Pattern] = re.compile(
    r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})"
    + r"\smac:\s(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))"
    + r"\svalid\sfor:\s(?P<timevalid>(-?\d+))"
    + r"\ssec"
)
