"""Custom types for the Tewke integration."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytewke
    from pytewke.data import Scene

    from homeassistant.config_entries import ConfigEntry

    from .coordinator import TewkeCoordinator

type TewkeConfigEntry = ConfigEntry[TewkeData]


@dataclass
class TewkeData:
    """Data for the Tewke integration."""

    host: str
    tap: pytewke.Tap
    coordinator: TewkeCoordinator
    scenes: dict[str, Scene]
    pending_scenes: dict[str, Scene] = field(default_factory=dict)
    observe_active: bool = False
