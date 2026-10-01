"""Assumed Gree state shared within one config entry."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .climate import GreeAcClimateEntity
    from .switch import GreeAcOptionSwitch


class GreeAcState:
    """Assumed Gree state shared within one config entry."""

    def __init__(self) -> None:
        """Initialize one entry's state and serialized command lock."""
        self.turbo: bool = False
        self.light: bool = True
        self.health: bool = False
        self.xfan: bool = False
        self.climate: GreeAcClimateEntity | None = None
        self.switches: list[GreeAcOptionSwitch] = []
        self.command_lock = asyncio.Lock()
