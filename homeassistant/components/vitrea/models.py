"""Data models for Vitrea integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from vitreaclient import VitreaClient

    from .coordinator import VitreaCoordinator

type VitreaConfigEntry = ConfigEntry[VitreaRuntimeData]


@dataclass
class VitreaRuntimeData:
    """Runtime data for Vitrea integration."""

    client: VitreaClient
    coordinator: VitreaCoordinator
    hass: HomeAssistant
