"""
Support for Tuya fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.tuya/
"""

from homeassistant.components.fan import (
    ENTITY_ID_FORMAT, FanEntity, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED)
from homeassistant.components.tuya import DATA_TUYA, TuyaDevice
from homeassistant.const import STATE_OFF

DEPENDENCIES = ['tuya']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya fan platform."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get('dev_ids')
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaFanDevice(device))
    add_devices(devices)


class TuyaFanDevice(TuyaDevice, FanEntity):
    """Tuya fan devices."""

    def __init__(self, tuya):
        """Init Tuya fan device."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self.speeds = [STATE_OFF]

    async def async_added_to_hass(self):
        """Create fan list when add to hass."""
        await super().async_added_to_hass()
        self.speeds.extend(self.tuya.speed_list())

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed == STATE_OFF:
            self.turn_off()
        else:
            self.tuya.set_speed(speed)

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed is not None:
            self.set_speed(speed)
        else:
            self.tuya.turn_on()

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.tuya.turn_off()

    def oscillate(self, oscillating) -> None:
        """Oscillate the fan."""
        self.tuya.oscillate(oscillating)

    @property
    def oscillating(self):
        """Return current oscillating status."""
        if self.supported_features & SUPPORT_OSCILLATE == 0:
            return None
        if self.speed == STATE_OFF:
            return False
        return self.tuya.oscillating()

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self.tuya.state()

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self.is_on:
            return self.tuya.speed()
        return STATE_OFF

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self.speeds

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supports = SUPPORT_SET_SPEED
        if self.tuya.support_oscillate():
            supports = supports | SUPPORT_OSCILLATE
        return supports
