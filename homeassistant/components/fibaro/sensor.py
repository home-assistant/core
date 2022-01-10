"""Support for Fibaro sensors."""
from __future__ import annotations

from contextlib import suppress

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FIBARO_DEVICES, FibaroDevice

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "com.fibaro.temperatureSensor": SensorEntityDescription(
        key="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "com.fibaro.smokeSensor": SensorEntityDescription(
        key="Smoke",
        icon="mdi:fire",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "CO2": SensorEntityDescription(
        key="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
    ),
    "com.fibaro.humiditySensor": SensorEntityDescription(
        key="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    "com.fibaro.lightSensor": SensorEntityDescription(
        key="Light",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
    "unknown": SensorEntityDescription(key="Unknown"),
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroSensor(device) for device in hass.data[FIBARO_DEVICES]["sensor"]], True
    )


class FibaroSensor(FibaroDevice, SensorEntity):
    """Representation of a Fibaro Sensor."""

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        super().__init__(fibaro_device)
        self.entity_id = f"{DOMAIN}.{self.ha_id}"
        if fibaro_device.type in SENSOR_TYPES:
            self.entity_description = SENSOR_TYPES[fibaro_device.type]
        else:
            self.entity_description = SENSOR_TYPES["unknown"]

        with suppress(KeyError, ValueError):
            if not self.entyty_description.native_unit_of_measurement:
                if self.fibaro_device.properties.unit == "lux":
                    self._attr_native_unit_of_measurement = LIGHT_LUX
                elif self.fibaro_device.properties.unit == "C":
                    self._attr_native_unit_of_measurement = TEMP_CELSIUS
                elif self.fibaro_device.properties.unit == "F":
                    self._attr_native_unit_of_measurement = TEMP_FAHRENHEIT
                else:
                    self._attr_native_unit_of_measurement = (
                        self.fibaro_device.properties.unit
                    )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.current_value

    def update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            self.current_value = float(self.fibaro_device.properties.value)
