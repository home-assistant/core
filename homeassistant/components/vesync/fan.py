"""Support for VeSync fans."""
import logging
import math

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_FANS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LV-PUR131S": "fan",
    "Classic300S": "fan",
    "Core200S": "fan",
    "Core300S": "fan",
    "Core400S": "fan",
}

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"

PRESET_MODES = {
    "LV-PUR131S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Classic300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core200S": [FAN_MODE_SLEEP],
    "Core300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core400S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
}
SPEED_RANGE = (1, 3)  # off is not included
MIST_RANGE = (1, 9)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_FANS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_FANS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "fan":
            entities.append(VeSyncFanHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncFanHA(VeSyncDevice, FanEntity):
    """Representation of a VeSync fan."""

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan

    @property
    def is_fan(self):
        """Return if this is a fan or humidifier."""
        return hasattr(self.smartfan, "change_fan_speed")

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def percentage(self):
        """Return the current speed."""
        if (
            self.smartfan.mode == "manual"
            and (current_level := self.smartfan.fan_level) is not None
        ):
            return ranged_value_to_percentage(SPEED_RANGE, current_level)
        if (
            self.smartfan.details.get("mode", None) == "manual"
            and (current_level := self.smartfan.details.get("mist_level", None))
            is not None
        ):
            return ranged_value_to_percentage(MIST_RANGE, current_level)
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self.is_fan:
            return int_states_in_range(SPEED_RANGE)
        return int_states_in_range(MIST_RANGE)

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return PRESET_MODES[self.device.device_type]

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        if self.is_fan:
            if self.smartfan.mode in (FAN_MODE_AUTO, FAN_MODE_SLEEP):
                return self.smartfan.mode
        else:
            if (current_mode := self.smartfan.details.get("mode", None)) in (
                FAN_MODE_AUTO,
                FAN_MODE_SLEEP,
            ):
                return current_mode
        return None

    @property
    def unique_info(self):
        """Return the ID of this fan."""
        return self.smartfan.uuid

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the fan."""
        attr = {}

        if hasattr(self.smartfan, "active_time"):
            attr["active_time"] = self.smartfan.active_time

        if hasattr(self.smartfan, "screen_status"):
            attr["screen_status"] = self.smartfan.screen_status

        if hasattr(self.smartfan, "child_lock"):
            attr["child_lock"] = self.smartfan.child_lock

        if hasattr(self.smartfan, "night_light"):
            attr["night_light"] = self.smartfan.night_light

        if hasattr(self.smartfan, "air_quality"):
            attr["air_quality"] = self.smartfan.air_quality

        if hasattr(self.smartfan, "mode"):
            attr["mode"] = self.smartfan.mode

        if self.smartfan.details.get("mode", None) is not None:
            attr["mode"] = self.smartfan.details["mode"]

        if hasattr(self.smartfan, "filter_life"):
            attr["filter_life"] = self.smartfan.filter_life

        if self.smartfan.details.get("mist_level", None) is not None:
            attr["mist_level"] = self.smartfan.details["mist_level"]

        if self.smartfan.details.get("humidity", None) is not None:
            attr["humidity"] = self.smartfan.details["humidity"]

        if self.smartfan.details.get("water_lacks", None) is not None:
            attr["tank_empty"] = self.smartfan.details["water_lacks"]

        if self.smartfan.details.get("water_tank_lifted", None) is not None:
            attr["tank_removed"] = self.smartfan.details["water_tank_lifted"]

        return attr

    def set_percentage(self, percentage):
        """Set the speed of the device."""
        if percentage == 0:
            self.smartfan.turn_off()
            return

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        if self.is_fan:
            self.smartfan.manual_mode()
            self.smartfan.change_fan_speed(
                math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            )
            self.schedule_update_ha_state()
        else:
            self.smartfan.set_mist_level(
                math.ceil(percentage_to_ranged_value(MIST_RANGE, percentage))
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

        if preset_mode == FAN_MODE_AUTO:
            if self.is_fan:
                self.smartfan.auto_mode()
            else:
                self.smartfan.set_humidity_mode(FAN_MODE_AUTO)
        elif preset_mode == FAN_MODE_SLEEP:
            if self.is_fan:
                self.smartfan.sleep_mode()
            else:
                self.smartfan.set_humidity_mode(FAN_MODE_SLEEP)

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
        if percentage is None:
            percentage = 50
        self.set_percentage(percentage)
