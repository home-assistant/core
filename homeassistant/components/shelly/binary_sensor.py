"""Binary sensor for Shelly."""
import aioshelly

from homeassistant.components import binary_sensor
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity import Entity

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN

SENSORS = {
    "dwIsOpened": binary_sensor.DEVICE_CLASS_OPENING,
    "flood": binary_sensor.DEVICE_CLASS_MOISTURE,
    "overpower": None,
    "smoke": binary_sensor.DEVICE_CLASS_SMOKE,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []

    for block in wrapper.device.blocks:
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
        device_class = SENSORS[attribute]

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
        return STATE_ON if getattr(self.block, self.attribute) else STATE_OFF

    @property
    def device_class(self):
        """Device class of sensor."""
        return self._device_class
