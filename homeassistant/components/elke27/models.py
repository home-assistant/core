"""Models for the Elke27 integration."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import Elke27DataUpdateCoordinator
from .hub import Elke27Hub


@dataclass(slots=True)
class Elke27RuntimeData:
    """Runtime data stored on the config entry."""

    hub: Elke27Hub
    coordinator: Elke27DataUpdateCoordinator
