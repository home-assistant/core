"""Models for the HomeKit component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
