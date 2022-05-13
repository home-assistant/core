"""Support for VeSync fans."""
import logging
import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
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
    "LV-RH131S": "fan",  # Alt ID Model LV-PUR131S
    "Core200S": "fan",
    "LAP-C201S-AUSR": "fan",  # Alt ID Model Core200S
    "LAP-C202S-WUSR": "fan",  # Alt ID Model Core200S
    "Core300S": "fan",
    "LAP-C301S-WJP": "fan",  # Alt ID Model Core300S
    "Core400S": "fan",
    "LAP-C401S-WJP": "fan",  # Alt ID Model Core400S
    "LAP-C401S-WUSR": "fan",  # Alt ID Model Core400S
    "LAP-C401S-WAAA": "fan",  # Alt ID Model Core400S
    "Core600S": "fan",
    "LAP-C601S-WUS": "fan",  # Alt ID Model Core600S
    "LAP-C601S-WUSR": "fan",  # Alt ID Model Core600S
    "LAP-C601S-WEU": "fan",  # Alt ID Model Core600S
}

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"

PRESET_MODES = {
    "LV-PUR131S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "LV-RH131S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model LV-PUR131S
    "Core200S": [FAN_MODE_SLEEP],
    "LAP-C201S-AUSR": [FAN_MODE_SLEEP],  # Alt ID Model Core200S
    "LAP-C202S-WUSR": [FAN_MODE_SLEEP],  # Alt ID Model Core200S
    "Core300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "LAP-C301S-WJP": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core300S
    "Core400S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "LAP-C401S-WJP": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core400S
    "LAP-C401S-WUSR": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core400S
    "LAP-C401S-WAAA": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core400S
    "Core600S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "LAP-C601S-WUS": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core600S
    "LAP-C601S-WUSR": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core600S
    "LAP-C601S-WEU": [FAN_MODE_AUTO, FAN_MODE_SLEEP],  # Alt ID Model Core600S
}
SPEED_RANGE = {  # off is not included
    "LV-PUR131S": (1, 3),
    "LV-RH131S": (1, 3),  # ALt ID Model LV-PUR131S
    "Core200S": (1, 3),
    "LAP-C201S-AUSR": (1, 3),  # ALt ID Model Core200S
    "LAP-C202S-WUSR": (1, 3),  # ALt ID Model Core200S
    "Core300S": (1, 3),
    "LAP-C301S-WJP": (1, 3),  # ALt ID Model Core300S
    "Core400S": (1, 4),
    "LAP-C401S-WJP": (1, 4),  # ALt ID Model Core400S
    "LAP-C401S-WUSR": (1, 4),  # ALt ID Model Core400S
    "LAP-C401S-WAAA": (1, 4),  # ALt ID Model Core400S
    "Core600S": (1, 4),
    "LAP-C601S-WUS": (1, 4),  # ALt ID Model Core600S
    "LAP-C601S-WUSR": (1, 4),  # ALt ID Model Core600S
    "LAP-C601S-WEU": (1, 4),  # ALt ID Model Core600S
}


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

    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, fan):
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self.smartfan = fan

    @property
    def percentage(self):
        """Return the current speed."""
        if (
            self.smartfan.mode == "manual"
            and (current_level := self.smartfan.fan_level) is not None
        ):
            return ranged_value_to_percentage(
                SPEED_RANGE[self.device.device_type], current_level
            )
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE[self.device.device_type])

    @property
    def preset_modes(self):
        """Get the list of available preset modes."""
        return PRESET_MODES[self.device.device_type]

    @property
    def preset_mode(self):
        """Get the current preset mode."""
        if self.smartfan.mode in (FAN_MODE_AUTO, FAN_MODE_SLEEP):
            return self.smartfan.mode
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

        if self.smartfan.details.get("air_quality_value") is not None:
            attr["air_quality_value"] = self.smartfan.details["air_quality"]

        if hasattr(self.smartfan, "mode"):
            attr["mode"] = self.smartfan.mode

        if hasattr(self.smartfan, "filter_life"):
            attr["filter_life"] = self.smartfan.filter_life

        return attr

    def set_percentage(self, percentage):
        """Set the speed of the device."""
        if percentage == 0:
            self.smartfan.turn_off()
            return

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        self.smartfan.manual_mode()
        self.smartfan.change_fan_speed(
            math.ceil(
                percentage_to_ranged_value(
                    SPEED_RANGE[self.device.device_type], percentage
                )
            )
        )
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode):
        """Set the preset mode of device."""
        if preset_mode not in self.preset_modes:
            raise ValueError(
                f"{preset_mode} is not one of the valid preset modes: "
                f"{self.preset_modes}"
            )

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        if preset_mode == FAN_MODE_AUTO:
            self.smartfan.auto_mode()
        elif preset_mode == FAN_MODE_SLEEP:
            self.smartfan.sleep_mode()

        self.schedule_update_ha_state()

    def turn_on(
        self,
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
