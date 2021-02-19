"""Support for VeSync fans."""
import logging
import math

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_FANS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LV-PUR131S": "fan",
}

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"

PRESET_MODES = [FAN_MODE_AUTO, FAN_MODE_SLEEP]
SPEED_RANGE = (1, 3)  # off is not included


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the VeSync fan platform."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_FANS), async_discover)
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_FANS], async_add_entities)


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
    def percentage(self):
        """Return the current speed."""
        if self.smartfan.mode == "manual":
            current_level = self.smartfan.fan_level
            if current_level is not None:
                return ranged_value_to_percentage(SPEED_RANGE, current_level)
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return PRESET_MODES

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        if self.smartfan.mode == FAN_MODE_AUTO:
            return FAN_MODE_AUTO
        return None

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

    def set_percentage(self, percentage):
        """Set the speed of the device."""
        if percentage == 0:
            self.smartfan.turn_off()
            return

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        self.smartfan.manual_mode()
        self.smartfan.change_fan_speed(
            math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        )
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode):
        """Set the preset mode of device."""
        if preset_mode not in self.preset_modes:
            raise ValueError(
                "{preset_mode} is not one of the valid preset modes: {self.preset_modes}"
            )

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        self.smartfan.auto_mode()
        self.schedule_update_ha_state()

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return
        self.set_percentage(percentage)
