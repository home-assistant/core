"""Support for Ecowitt Weather Stations."""

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

ECOWITT_BINARYSENSORS_MAPPING = {
    EcoWittSensorTypes.LEAK: (BinarySensorDeviceClass.MOISTURE,),
    EcoWittSensorTypes.BATTERY_BINARY: (BinarySensorDeviceClass.BATTERY,),
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
        description = BinarySensorEntityDescription(
            key=sensor.key,
            name=sensor.name,
            device_class=mapping[0],
        )

        async_add_entities([EcowittBinarySensorEntity(sensor, description)])

    ecowitt.new_sensor_cb.append(_new_sensor)

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
        if self.ecowitt.value > 0:
            return True
        return False
