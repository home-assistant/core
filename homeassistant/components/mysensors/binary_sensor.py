"""Support for MySensors binary sensors."""
from homeassistant.components import mysensors
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SOUND,
    DEVICE_CLASS_VIBRATION,
    DEVICE_CLASSES,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.const import STATE_ON

SENSORS = {
    "S_DOOR": "door",
    "S_MOTION": "motion",
    "S_SMOKE": "smoke",
    "S_SPRINKLER": DEVICE_CLASS_SAFETY,
    "S_WATER_LEAK": DEVICE_CLASS_SAFETY,
    "S_SOUND": DEVICE_CLASS_SOUND,
    "S_VIBRATION": DEVICE_CLASS_VIBRATION,
    "S_MOISTURE": "moisture",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the mysensors platform for binary sensors."""
    mysensors.setup_mysensors_platform(
        hass,
        DOMAIN,
        discovery_info,
        MySensorsBinarySensor,
        async_add_entities=async_add_entities,
    )


class MySensorsBinarySensor(mysensors.device.MySensorsEntity, BinarySensorEntity):
    """Representation of a MySensors Binary Sensor child node."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._values.get(self.value_type) == STATE_ON

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        pres = self.gateway.const.Presentation
        device_class = SENSORS.get(pres(self.child_type).name)
        if device_class in DEVICE_CLASSES:
            return device_class
        return None
