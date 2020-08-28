"""Sensor for Shelly."""
import aioshelly

from homeassistant.components import sensor
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN

SENSORS = {
    "extTemp": [None, sensor.DEVICE_CLASS_TEMPERATURE],
    "humidity": [UNIT_PERCENTAGE, sensor.DEVICE_CLASS_HUMIDITY],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []

    for block in wrapper.device.blocks:
        if block.type != "sensor":
            continue

        for attr in SENSORS:
            if not hasattr(block, attr):
                continue

            sensors.append(ShellySensor(wrapper, block, attr))

    if sensors:
        async_add_entities(sensors)


class ShellySensor(ShellyBlockEntity, Entity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(
        self,
        wrapper: ShellyDeviceWrapper,
        block: aioshelly.Block,
        attribute: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(wrapper, block)
        self.attribute = attribute
        unit, device_class = SENSORS[attribute]
        info = block.info(attribute)

        if info[aioshelly.BLOCK_VALUE_TYPE] == aioshelly.BLOCK_VALUE_TYPE_TEMPERATURE:
            if info[aioshelly.BLOCK_VALUE_UNIT] == "C":
                unit = TEMP_CELSIUS
            else:
                unit = TEMP_FAHRENHEIT

        self._unit = unit
        self._device_class = device_class

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{super().unique_id}-{self.attribute}"

    @property
    def name(self):
        """Name of sensor."""
        return f"{self.wrapper.name} - {self.attribute}"

    @property
    def state(self):
        """Value of sensor."""
        return getattr(self.block, self.attribute)

    @property
    def unit_of_measurement(self):
        """Return unit of sensor."""
        return self._unit

    @property
    def device_class(self):
        """Device class of sensor."""
        return self._device_class
