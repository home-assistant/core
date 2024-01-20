"""Define RainMachine data models."""
from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription


@dataclass(frozen=True, kw_only=True)
class RainMachineEntityDescription(EntityDescription):
    """Describe a RainMachine entity."""

    api_category: str
