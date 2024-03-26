"""Models for the HomeKit component."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import HomeKit


@dataclass
class HomeKitEntryData:
    """Class to hold HomeKit data."""

    homekit: "HomeKit"
    pairing_qr: bytes | None = None
    pairing_qr_secret: str | None = None
