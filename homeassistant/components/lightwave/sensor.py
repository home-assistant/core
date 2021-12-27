"""Support for LightwaveRF TRV - Associated Battery."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, PERCENTAGE

from . import CONF_SERIAL, LIGHTWAVE_LINK


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return battery."""
    if discovery_info is None:
        return

    batteries = []

    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_config in discovery_info.values():
        name = device_config[CONF_NAME]
        serial = device_config[CONF_SERIAL]
        batteries.append(LightwaveBattery(name, lwlink, serial))

    async_add_entities(batteries)


class LightwaveBattery(SensorEntity):
    """Lightwave TRV Battery."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, name, lwlink, serial):
        """Initialize the Lightwave Trv battery sensor."""
        self._attr_name = name
        self._lwlink = lwlink
        self._serial = serial
        self._attr_unique_id = f"{serial}-trv-battery"

    def update(self):
        """Communicate with a Lightwave RTF Proxy to get state."""
        (dummy_temp, dummy_targ, battery, dummy_output) = self._lwlink.read_trv_status(
            self._serial
        )
        self._attr_native_value = battery
