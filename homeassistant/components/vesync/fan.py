"""Support for VeSync fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .common import is_fan, is_purifier
from .const import (
    DOMAIN,
    SKU_TO_BASE_DEVICE,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_FAN_MODE_ADVANCED_SLEEP,
    VS_FAN_MODE_AUTO,
    VS_FAN_MODE_MANUAL,
    VS_FAN_MODE_NORMAL,
    VS_FAN_MODE_PET,
    VS_FAN_MODE_PRESET_LIST_HA,
    VS_FAN_MODE_SLEEP,
    VS_FAN_MODE_TURBO,
    VS_MANAGER,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = {  # off is not included
    "LV-PUR131S": (1, 3),
    "Core200S": (1, 3),
    "Core300S": (1, 3),
    "Core400S": (1, 4),
    "Core600S": (1, 4),
    "EverestAir": (1, 3),
    "Vital200S": (1, 4),
    "Vital100S": (1, 4),
    "SmartTowerFan": (1, 13),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][VS_MANAGER].devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: VeSyncDataCoordinator,
):
    """Check if device is fan and add entity."""

    async_add_entities(
        VeSyncFanHA(dev, coordinator)
        for dev in devices
        if is_fan(dev) or is_purifier(dev)
    )


class VeSyncFanHA(VeSyncBaseEntity, FanEntity):
    """Representation of a VeSync fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_name = None
    _attr_translation_key = "vesync"

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.state.device_status == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        if (
            self.device.state.mode == VS_FAN_MODE_MANUAL
            and (current_level := self.device.state.fan_level) is not None
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
        if hasattr(self.device, "modes"):
            return sorted(
                [
                    mode
                    for mode in self.device.modes
                    if mode in VS_FAN_MODE_PRESET_LIST_HA
                ]
            )
        return []

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if self.device.state.mode in VS_FAN_MODE_PRESET_LIST_HA:
            return self.device.state.mode
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the fan."""
        attr = {}

        if hasattr(self.device, "active_time"):
            attr["active_time"] = self.device.state.active_time

        if hasattr(self.device, "screen_status"):
            attr["screen_status"] = self.device.state.screen_status

        if hasattr(self.device, "child_lock"):
            attr["child_lock"] = self.device.state.child_lock

        if hasattr(self.device, "night_light"):
            attr["night_light"] = self.device.state.night_light

        if hasattr(self.device, "mode"):
            attr["mode"] = self.device.state.mode

        return attr

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the device."""
        if percentage == 0:
            success = await self.device.turn_off()
            if not success:
                raise HomeAssistantError("An error occurred while turning off.")
        elif not self.device.is_on:
            success = await self.device.turn_on()
            if not success:
                raise HomeAssistantError("An error occurred while turning on.")

        success = await self.device.manual_mode()
        if not success:
            raise HomeAssistantError("An error occurred while manual mode.")
        success = self.device.change_fan_speed(
            math.ceil(
                percentage_to_ranged_value(
                    SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]], percentage
                )
            )
        )
        if not success:
            raise HomeAssistantError("An error occurred while changing fan speed.")
        self.schedule_update_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of device."""
        if preset_mode not in VS_FAN_MODE_PRESET_LIST_HA:
            raise ValueError(
                f"{preset_mode} is not one of the valid preset modes: "
                f"{VS_FAN_MODE_PRESET_LIST_HA}"
            )

        if not self.device.is_on:
            await self.device.turn_on()

        if preset_mode == VS_FAN_MODE_AUTO:
            success = await self.device.auto_mode()
        elif preset_mode == VS_FAN_MODE_SLEEP:
            success = await self.device.sleep_mode()
        elif preset_mode == VS_FAN_MODE_ADVANCED_SLEEP:
            success = await self.device.advanced_sleep_mode()
        elif preset_mode == VS_FAN_MODE_PET:
            success = await self.device.pet_mode()
        elif preset_mode == VS_FAN_MODE_TURBO:
            success = await self.device.turbo_mode()
        elif preset_mode == VS_FAN_MODE_NORMAL:
            success = await self.device.normal_mode()
        if not success:
            raise HomeAssistantError("An error occurred while setting preset mode.")

        self.schedule_update_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage is None:
            percentage = 50
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        success = await self.device.turn_off()
        if not success:
            raise HomeAssistantError("An error occurred while turning off.")
        self.schedule_update_ha_state()
