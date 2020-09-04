"""Support for VeSync fans."""
import logging

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_FANS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LV-PUR131S": "fan",
}

SPEED_AUTO = "auto"
FAN_SPEEDS = [SPEED_AUTO, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the VeSync fan platform."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_FANS), async_discover)
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_FANS], async_add_entities)
    return True


@callback
def _async_setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    dev_list = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "fan":
            dev_list.append(VeSyncFanHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(dev_list, update_before_add=True)


class VeSyncFanHA(VeSyncDevice, FanEntity):
    """Representation of a VeSync fan."""

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self):
        """Return the current speed."""
        if self.smartfan.mode == SPEED_AUTO:
            return SPEED_AUTO
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
    def device_state_attributes(self):
        """Return the state attributes of the fan."""
        return {
            "mode": self.smartfan.mode,
            "active_time": self.smartfan.active_time,
            "filter_life": self.smartfan.filter_life,
            "air_quality": self.smartfan.air_quality,
            "screen_status": self.smartfan.screen_status,
        }

    def set_speed(self, speed):
        """Set the speed of the device."""
        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        if speed is None or speed == SPEED_AUTO:
            self.smartfan.auto_mode()
        else:
            self.smartfan.manual_mode()
            self.smartfan.change_fan_speed(FAN_SPEEDS.index(speed))

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the device on."""
        self.smartfan.turn_on()
        self.set_speed(speed)
