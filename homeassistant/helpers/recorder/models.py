"""Recorder models."""

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecorderData:
    """Recorder data stored in hass.data."""

    recorder_platforms: dict[str, Any] = field(default_factory=dict)
    db_connected: asyncio.Future = field(default_factory=asyncio.Future)
