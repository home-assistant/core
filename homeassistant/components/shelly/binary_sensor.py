"""Binary sensor for Shelly."""
import aioshelly

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_VIBRATION,
    BinarySensorEntity,
)

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN

SENSORS = {
    "dwIsOpened": DEVICE_CLASS_OPENING,
    "flood": DEVICE_CLASS_MOISTURE,
    "gas": DEVICE_CLASS_GAS,
    "overpower": None,
    "overtemp": None,
    "smoke": DEVICE_CLASS_SMOKE,
    "vibration": DEVICE_CLASS_VIBRATION,
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


class ShellySensor(ShellyBlockEntity, BinarySensorEntity):
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
    def is_on(self):
        """Return true if sensor state is on."""
        if self.attribute == "gas":
            # Gas sensor value of Shelly Gas can be none/mild/heavy/test. We return True
            # when the value is mild or heavy.
            return getattr(self.block, self.attribute) in ["mild", "heavy"]
        return bool(getattr(self.block, self.attribute))

    @property
    def device_class(self):
        """Device class of sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.attribute == "gas":
            # We return raw value of the gas sensor as an attribute.
            return {"detected": getattr(self.block, self.attribute)}

    @property
    def available(self):
        """Available."""
        if self.attribute == "gas":
            # "sensorOp" is "normal" when Shelly Gas is working properly and taking
            # measurements.
            return super().available and self.block.sensorOp == "normal"
        return super().available
