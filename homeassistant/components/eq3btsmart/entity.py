"""Base class for all eQ-3 entities."""

from homeassistant.helpers.entity import Entity

from . import Eq3ConfigEntry


class Eq3Entity(Entity):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: Eq3ConfigEntry) -> None:
        """Initialize the eq3 entity."""

        self._eq3_config = entry.runtime_data.eq3_config
        self._thermostat = entry.runtime_data.thermostat
