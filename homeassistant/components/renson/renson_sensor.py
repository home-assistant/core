"""Sensor class of the Renson ventilation system."""
from renson_endura_delta.general_enum import DataType
import renson_endura_delta.renson as renson

from homeassistant.components.renson.renson_descriptions import (
    RensonSensorEntityDescription,
)
from homeassistant.components.sensor import SensorEntity


class RensonSensor(SensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: RensonSensorEntityDescription,
        renson_api: renson.RensonVentilation,
    ) -> None:
        """Initialize class."""
        super().__init__()

        self._state = None
        self.entity_description = description
        self.field = description.field
        self.data_type = description.field.field_type
        self.renson_api = renson_api
        self.raw_format = description.raw_format

    @property
    def state(self):
        """Lookup the state of the sensor and save it."""
        return self._state

    def update(self):
        """Save state of sensor."""
        if self.raw_format:
            self._state = self.renson_api.get_data_string(self.field)
        else:
            if self.data_type == DataType.NUMERIC:
                self._state = self.renson_api.get_data_numeric(self.field)
            elif self.data_type == DataType.STRING:
                self._state = self.renson_api.get_data_string(self.field)

            elif self.data_type == DataType.LEVEL:
                self._state = self.renson_api.get_data_level(self.field).value

            elif self.data_type == DataType.BOOLEAN:
                self._state = self.renson_api.get_data_boolean(self.field)

            elif self.data_type == DataType.QUALITY:
                self._state = self.renson_api.get_data_quality(self.field).value
