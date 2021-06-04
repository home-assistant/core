"""Models for nmap platform."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple


class Device(NamedTuple):
    """Named tuple to represent a nmap device."""

    mac: str
    name: str
    ip: str
    last_update: datetime
