"""Support for VeSync fans."""
from __future__ import annotations

import logging
import math
from typing import Any

from pyvesync.vesyncfan import VeSyncAirBypass

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
from .const import DEV_TYPE_TO_HA, DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_FANS

_LOGGER = logging.getLogger(__name__)

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"

PRESET_MODES = {
    "LV-PUR131S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core200S": [FAN_MODE_SLEEP],
    "Core300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core400S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core600S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
}
SPEED_RANGE = {  # off is not included
    "LV-PUR131S": (1, 3),
    "Core200S": (1, 3),
    "Core300S": (1, 3),
    "Core400S": (1, 4),
    "Core600S": (1, 4),
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
        entities = []
        for dev in devices:
            if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type)) == "fan":
                entities.append(VeSyncFanHA(dev))
            else:
                _LOGGER.warning(
                    "%s - Unknown device type - %s", dev.device_name, dev.device_type
                )
                continue

        async_add_entities(entities, update_before_add=True)

    discover(hass.data[DOMAIN][VS_FANS])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_FANS), discover)
    )


class VeSyncFanHA(VeSyncDevice, FanEntity):
    """Representation of a VeSync fan."""

    device: VeSyncAirBypass

    def __init__(self, fan) -> None:
        """Initialize the VeSync fan device."""
        super().__init__(fan)
        self._attr_supported_features = FanEntityFeature.SET_SPEED

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        if (
            self.device.mode == "manual"
            and (current_level := self.device.fan_level) is not None
        ):
            return ranged_value_to_percentage(
                SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]], current_level
            )
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(
            SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]]
        )

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return PRESET_MODES[SKU_TO_BASE_DEVICE[self.device.device_type]]

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if self.device.mode in self.preset_modes:
            return self.device.mode
        return None

    @property
    def unique_info(self):
        """Return the ID of this fan."""
        return self.device.uuid

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the fan."""
        attr = {}

        if hasattr(self.device, "active_time"):
            attr["active_time"] = self.device.active_time

        if hasattr(self.device, "screen_status"):
            attr["screen_status"] = self.device.screen_status

        if hasattr(self.device, "child_lock"):
            attr["child_lock"] = self.device.child_lock

        if hasattr(self.device, "night_light"):
            attr["night_light"] = self.device.night_light

        if hasattr(self.device, "mode"):
            attr["mode"] = self.device.mode

        return attr

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the device."""
        if percentage == 0:
            self.device.turn_off()
            self.schedule_update_ha_state()
            return

        if not self.device.is_on:
            self.device.turn_on()

        self.device.manual_mode()
        self.device.change_fan_speed(
            math.ceil(
                percentage_to_ranged_value(
                    SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]], percentage
                )
            )
        )
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of device."""
        if preset_mode not in self.preset_modes:
            raise ValueError(
                f"{preset_mode} is not one of the valid preset modes: "
                f"{self.preset_modes}"
            )

        if not self.device.is_on:
            self.device.turn_on()

        if preset_mode == FAN_MODE_AUTO:
            self.device.auto_mode()
        elif preset_mode == FAN_MODE_SLEEP:
            self.device.sleep_mode()

        self.schedule_update_ha_state()

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return
        if percentage is None:
            percentage = 50
        self.set_percentage(percentage)
