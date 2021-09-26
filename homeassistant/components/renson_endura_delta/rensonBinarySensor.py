"""Renson Binary sensor."""
from rensonVentilationLib.fieldEnum import FieldEnum
import rensonVentilationLib.renson as renson

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)


class RensonBinarySensor(BinarySensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: BinarySensorEntityDescription,
        field: FieldEnum,
        rensonApi: renson.RensonVentilation,
    ):
        """Initialize class."""
        self._state = None
        self.renson = rensonApi
        self.field = field
        self.entity_description = description

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get binary data and save it in state."""
        self._state = self.renson.get_data_boolean(self.field)
