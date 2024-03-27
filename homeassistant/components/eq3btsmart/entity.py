"""Base class for all eQ-3 entities."""

from eq3btsmart.thermostat import Thermostat

from homeassistant.helpers.entity import Entity

from .models import Eq3Config


class Eq3Entity(Entity):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the eq3 entity."""

        self._eq3_config = eq3_config
        self._thermostat = thermostat
