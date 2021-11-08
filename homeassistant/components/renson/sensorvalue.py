"""Sensor class of the Renson ventilation system."""
from rensonVentilationLib.fieldEnum import FieldEnum
from rensonVentilationLib.generalEnum import DataType
import rensonVentilationLib.renson as renson

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription


class SensorValue(SensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: SensorEntityDescription,
        field: FieldEnum,
        renson: renson.RensonVentilation,
        rawFormat: bool,
    ):
        """Initialize class."""
        super().__init__()

        self._state = None
        self.entity_description = description
        self.field = field
        self.dataType = field.field_type
        self.renson = renson
        self.rawFormat = rawFormat

    @property
    def state(self):
        """Lookup the state of the sensor and save it."""
        return self._state

    def update(self):
        """Save state of sensor."""
        if self.rawFormat:
            self._state = self.renson.get_data_string(self.field)
        else:
            if self.dataType == DataType.NUMERIC:
                self._state = self.renson.get_data_numeric(self.field)
            elif self.dataType == DataType.STRING:
                self._state = self.renson.get_data_string(self.field)

            elif self.dataType == DataType.LEVEL:
                self._state = self.renson.get_data_level(self.field)

            elif self.dataType == DataType.BOOLEAN:
                self._state = self.renson.get_data_boolean(self.field)

            elif self.dataType == DataType.QUALITY:
                self._state = self.renson.get_data_quality(self.field)
