"""Runtime data dataclass for the Bosch SHC integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from boschshcpy import SHCSession
from homeassistant.helpers.device_registry import DeviceEntry


@dataclass
class SHCData:
    """Runtime data stored on the config entry."""

    session: SHCSession
    shc_device: DeviceEntry
    title: str
    polling_handler: Callable[[], None] | None = field(default=None)
    cert_check_unsub: Callable[[], None] | None = field(default=None)
    presence_unsub: Callable[[], None] | None = field(default=None)
    silent_mode_unsubs: list[Callable[[], None]] = field(default_factory=list)
