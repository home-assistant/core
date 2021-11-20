"""Binary sensor for renson."""

import renson_endura_delta.renson as renson

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.renson.renson_descriptions import (
    RensonBinarySensorEntityDescription,
)


class RensonBinarySensor(BinarySensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: RensonBinarySensorEntityDescription,
        rensonApi: renson.RensonVentilation,
    ) -> None:
        """Initialize class."""
        self._state = None
        self.renson = rensonApi
        self.field = description.field
        self.entity_description = description

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get binary data and save it in state."""
        self._state = self.renson.get_data_boolean(self.field)
