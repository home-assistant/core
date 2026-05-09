"""Custom types for adam_audio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .client import AdamAudioClient
    from .coordinator import AdamAudioCoordinator


type AdamAudioConfigEntry = ConfigEntry[AdamAudioData]


@dataclass
class AdamAudioData:
    """Data for the ADAM Audio integration."""

    client: AdamAudioClient
    coordinator: AdamAudioCoordinator


@dataclass
class AdamAudioIntegrationData:
    """Integration-wide data stored in hass.data[DOMAIN]."""

    coordinators: dict[str, AdamAudioCoordinator]
    group_switches_added: bool = False
    group_numbers_added: bool = False
    group_selects_added: bool = False
