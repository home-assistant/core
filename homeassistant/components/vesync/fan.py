"""Support for VeSync fans."""

from __future__ import annotations

import logging
from typing import Any

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .common import is_fan, is_purifier
from .const import (
    DOMAIN,
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
        """Return the currently set speed."""

        current_level = self.device.state.fan_level

        if self.device.state.mode == VS_FAN_MODE_MANUAL and current_level is not None:
            return ordered_list_item_to_percentage(
                self.device.fan_levels, current_level
            )
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self.device.fan_levels)

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        if hasattr(self.device, "modes"):
            return sorted(
                [
                    mode.value
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

        if hasattr(self.device.state, "active_time"):
            attr["active_time"] = self.device.state.active_time

        if (
            hasattr(self.device.state, "display_status")
            and self.device.state.display_status is not None
        ):
            attr["display_status"] = getattr(
                self.device.state.display_status, "value", None
            )

        if (
            hasattr(self.device.state, "child_lock")
            and self.device.state.child_lock is not None
        ):
            attr["child_lock"] = self.device.state.child_lock

        if (
            hasattr(self.device.state, "nightlight_status")
            and self.device.state.nightlight_status is not None
        ):
            attr["night_light"] = getattr(
                self.device.state.nightlight_status, "value", None
            )
        if hasattr(self.device.state, "mode"):
            attr["mode"] = self.device.state.mode

        return attr

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the device.

        If percentage is 0, turn off the fan. Otherwise, ensure the fan is on,
        set manual mode if needed, and set the speed.
        """
        if percentage == 0:
            # Turning off is a special case: do not set speed or mode
            if not await self.device.turn_off():
                raise HomeAssistantError(
                    "An error occurred while turning off: "
                    + self.device.last_response.message
                )
            self.schedule_update_ha_state()
            return

        # If the fan is off, turn it on first
        if not self.device.is_on:
            if not await self.device.turn_on():
                raise HomeAssistantError(
                    "An error occurred while turning on: "
                    + self.device.last_response.message
                )

        # Switch to manual mode if not already set
        if self.device.state.mode != VS_FAN_MODE_MANUAL:
            if not await self.device.set_manual_mode():
                raise HomeAssistantError(
                    "An error occurred while setting manual mode."
                    + self.device.last_response.message
                )

        # Calculate the speed level and set it
        if not await self.device.set_fan_speed(
            percentage_to_ordered_list_item(self.device.fan_levels, percentage)
        ):
            raise HomeAssistantError(
                "An error occurred while changing fan speed: "
                + self.device.last_response.message
            )

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
            raise HomeAssistantError(self.device.last_response.message)

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
            raise HomeAssistantError(self.device.last_response.message)
        self.schedule_update_ha_state()
