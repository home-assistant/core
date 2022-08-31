"""Support for Ecowitt Weather Stations."""
import dataclasses
from typing import Final

from aioecowitt import EcoWittListener, EcoWittSensor, EcoWittSensorTypes

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EcowittEntity

ECOWITT_BINARYSENSORS_MAPPING: Final = {
    EcoWittSensorTypes.LEAK: BinarySensorEntityDescription(
        key="LEAK", device_class=BinarySensorDeviceClass.MOISTURE
    ),
    EcoWittSensorTypes.BATTERY_BINARY: BinarySensorEntityDescription(
        key="BATTERY", device_class=BinarySensorDeviceClass.BATTERY
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add sensors if new."""
    ecowitt: EcoWittListener = hass.data[DOMAIN][entry.entry_id]

    def _new_sensor(sensor: EcoWittSensor) -> None:
        """Add new sensor."""
        if sensor.stype not in ECOWITT_BINARYSENSORS_MAPPING:
            return
        mapping = ECOWITT_BINARYSENSORS_MAPPING[sensor.stype]

        # Setup sensor description
        description = dataclasses.replace(
            mapping,
            key=sensor.key,
            name=sensor.name,
        )

        async_add_entities([EcowittBinarySensorEntity(sensor, description)])

    ecowitt.new_sensor_cb.append(_new_sensor)
    entry.async_on_unload(lambda: ecowitt.new_sensor_cb.remove(_new_sensor))

    # Add all sensors that are already known
    for sensor in ecowitt.sensors.values():
        _new_sensor(sensor)


class EcowittBinarySensorEntity(EcowittEntity, BinarySensorEntity):
    """Representation of a Ecowitt BinarySensor."""

    def __init__(
        self, sensor: EcoWittSensor, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(sensor)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.ecowitt.value > 0
