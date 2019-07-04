"""Support for VeSync Fans and Air Purifier."""
import logging

from homeassistant.components.fan import (FanEntity, SUPPORT_SET_SPEED)

from . import DOMAIN

from .common import CONF_FANS, async_add_entities_retry

_LOGGER = logging.getLogger(__name__)

FAN_SPEEDS = ["auto", "low", "medium", "high"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up fans."""
    await async_add_entities_retry(
        hass,
        async_add_entities,
        hass.data[DOMAIN][CONF_FANS],
        add_entity
    )
    return True


def add_entity(device, async_add_entities):
    """Check if device is online and add entity."""
    device.update()

    async_add_entities([VeSyncFanHA(device)], update_before_add=True)


class VeSyncFanHA(FanEntity):
    """Representation of a VeSync fan."""

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        self.smartfan = fan

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def is_on(self):
        """Return True if device is on."""
        return self.smartfan.device_status == "on"

    @property
    def speed(self):
        """Return the current speed."""
        if self.smartfan.mode == "auto":
            return "auto"
        if self.smartfan.mode == "manual":
            current_level = self.smartfan.fan_level
            if current_level is not None:
                return FAN_SPEEDS[current_level]
        return None

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return FAN_SPEEDS

    @property
    def unique_info(self):
        """Return the ID of this fan."""
        return self.smartfan.uuid

    @property
    def name(self):
        """Return the name of the fan."""
        return self.smartfan.device_name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the fan."""
        attr = {}
        attr['mode'] = self.smartfan.mode
        attr['active_time'] = self.smartfan.active_time
        attr['filter_life'] = self.smartfan.filter_life
        attr['air_quality'] = self.smartfan.air_quality
        attr['screen_status'] = self.smartfan.screen_status
        return attr

    def set_speed(self, speed):
        """Set fan speed."""
        if speed is None or speed == "auto":
            self.smartfan.auto_mode()
        else:
            self.smartfan.manual_mode()
            self.smartfan.change_fan_speed(FAN_SPEEDS.index(speed))

    # pylint: disable=arguments-differ
    def turn_on(self):
        """Turn vesync fan on."""
        self.smartfan.turn_on()

    def turn_off(self, **kwargs):
        """Turn vesync fan off."""
        self.smartfan.turn_off()

    def update(self):
        """Update vesync fan entity."""
        self.smartfan.update()
