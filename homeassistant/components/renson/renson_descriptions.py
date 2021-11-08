"""Renson sensor descriptions."""

from rensonVentilationLib.fieldEnum import FieldEnum

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription


class RensonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of binary sensor."""

    def __init__(self, key: str, name: str, field: FieldEnum) -> None:
        """Initialize class."""
        super().__init__(key=key)

        self.name = name
        self.field = field


class RensonSensorEntityDescription(SensorEntityDescription):
    """Description of sensor."""

    def __init__(
        self,
        key: str,
        name: str,
        field: FieldEnum,
        raw_format: bool,
        state_class: str = None,
        device_class: str = None,
        native_unit_of_measurement: str = None,
    ) -> None:
        """Initialize class."""
        super().__init__(
            key=key,
            state_class=state_class,
            device_class=device_class,
            native_unit_of_measurement=native_unit_of_measurement,
        )

        self.name = name
        self.field = field
        self.raw_format = raw_format
