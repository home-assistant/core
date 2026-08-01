"""Custom types for adam_audio."""

from dataclasses import dataclass

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
    # Entry whose platforms own the group entities; when it unloads, the
    # flags above are reset so another entry can recreate them.
    group_owner_entry_id: str | None = None
