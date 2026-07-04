"""Models for the HomeKit component."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from . import HomeKit

type HomeKitConfigEntry = ConfigEntry[HomeKitEntryData]


@dataclass
class HomeKitEntryData:
    """Class to hold HomeKit data."""

    homekit: HomeKit
    pairing_qr: bytes | None = None
    pairing_qr_secret: str | None = None
    last_options: dict[str, Any] = field(default_factory=dict)
