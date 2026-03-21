"""Models for the Growatt server integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import GrowattCoordinator


@dataclass
class GrowattRuntimeData:
    """Runtime data for the Growatt integration."""

    total_coordinator: GrowattCoordinator
    devices: dict[str, GrowattCoordinator]
    login_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_login_time: float | None = None
    api_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
