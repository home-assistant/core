"""Models for the Elke27 integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import Elke27DataUpdateCoordinator


@dataclass(slots=True)
class Elke27RuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: Elke27DataUpdateCoordinator


type Elke27ConfigEntry = ConfigEntry[Elke27RuntimeData]
