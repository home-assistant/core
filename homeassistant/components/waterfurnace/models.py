"""Models for the WaterFurnace integration."""

from __future__ import annotations

from dataclasses import dataclass

from waterfurnace.waterfurnace import WaterFurnace

from homeassistant.config_entries import ConfigEntry


@dataclass
class WaterFurnaceData:
    """Data for the WaterFurnace integration."""

    client: WaterFurnace
    gwid: str


type WaterFurnaceConfigEntry = ConfigEntry[WaterFurnaceData]
