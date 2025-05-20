"""Support for XS1 sensors."""

from __future__ import annotations

from xs1_api_client.api_constants import ActuatorType
from xs1_api_client.device.actuator import XS1Actuator
from xs1_api_client.device.sensor import XS1Sensor

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ACTUATORS, DOMAIN, SENSORS
from .entity import XS1DeviceEntity


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XS1 sensor platform."""
    sensors: list[XS1Sensor] = hass.data[DOMAIN][SENSORS]
    actuators: list[XS1Actuator] = hass.data[DOMAIN][ACTUATORS]

    sensor_entities = []
    for sensor in sensors:
        belongs_to_climate_actuator = False
        for actuator in actuators:
            if (
                actuator.type() == ActuatorType.TEMPERATURE
                and actuator.name() in sensor.name()
            ):
                belongs_to_climate_actuator = True
                break

        if not belongs_to_climate_actuator:
            sensor_entities.append(XS1SensorEntity(sensor))

    add_entities(sensor_entities)


class XS1SensorEntity(XS1DeviceEntity, SensorEntity):
    """Representation of a Sensor."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.device.value()

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self.device.unit()
