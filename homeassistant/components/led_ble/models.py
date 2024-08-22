"""The led ble integration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from led_ble import LEDBLE

    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class LEDBLEData:
    """Data for the led ble integration."""

    title: str
    device: LEDBLE
    coordinator: DataUpdateCoordinator[None]
