"""Models for laundrify platform."""

from __future__ import annotations

from typing import TypedDict


class LaundrifyDevice(TypedDict):
    """laundrify Power Plug."""

    _id: str
    name: str
    status: str
    firmwareVersion: str
