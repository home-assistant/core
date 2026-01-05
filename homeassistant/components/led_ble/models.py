"""The led ble integration models."""

from __future__ import annotations

from dataclasses import dataclass

from led_ble import LEDBLE

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

type LEDBLEConfigEntry = ConfigEntry[LEDBLEData]


@dataclass
class LEDBLEData:
    """Data for the led ble integration."""

    title: str
    device: LEDBLE
    coordinator: DataUpdateCoordinator[None]
