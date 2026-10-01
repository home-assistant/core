"""Assumed Gree state shared within one config entry."""

import asyncio
from typing import TYPE_CHECKING

from homeassistant.core import callback

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

    @callback
    def async_notify_switches(self) -> None:
        """Refresh every switch listening to this entry's state."""
        for switch in tuple(self.switches):
            switch.async_write_ha_state()
