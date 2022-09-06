"""BleBox sensor entities."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities

BLEBOX_TO_UNIT_MAP = {
    "celsius": TEMP_CELSIUS,
    "concentration_of_mp": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
}

BLEBOX_TO_SENSOR_DEVICE_CLASS = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "pm1": SensorDeviceClass.PM1,
    "pm2_5": SensorDeviceClass.PM25,
    "pm10": SensorDeviceClass.PM10,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxSensorEntity, "sensors"
    )


class BleBoxSensorEntity(BleBoxEntity, SensorEntity):
    """Representation of a BleBox sensor feature."""

    def __init__(self, feature):
        """Initialize a BleBox sensor feature."""
        super().__init__(feature)
        self._attr_native_unit_of_measurement = BLEBOX_TO_UNIT_MAP[feature.unit]
        self._attr_device_class = BLEBOX_TO_SENSOR_DEVICE_CLASS[feature.device_class]

    @property
    def native_value(self):
        """Return the state."""
        return self._feature.native_value
