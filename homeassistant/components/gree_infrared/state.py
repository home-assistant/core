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
        self.sleep: bool = False
        self.ifeel: bool = False
        self.swing_v: bool = False
        self.swing_h: bool = False
        self.swing_h_position: int = 0
        self.econo: bool = False
        self.fahrenheit: bool = False
        self.display_temp: int = 2
        self.swing_v_position: int | None = None
        self.fresh_air: int = 0
        self.timer_hours: float | None = None
        self.climate: GreeAcClimateEntity | None = None
        self.switches: list[GreeAcOptionSwitch] = []
        self.selects: list = []
        self.numbers: list = []
        self.command_lock = asyncio.Lock()

    @callback
    def async_notify_switches(self) -> None:
        """Refresh every option entity listening to this entry's state."""
        for entity in tuple(self.switches) + tuple(self.selects) + tuple(self.numbers):
            entity.async_write_ha_state()
