"""Support for Fjäråskupan fans."""

from __future__ import annotations

from typing import Any

from fjaraskupan import (
    COMMAND_AFTERCOOKINGTIMERAUTO,
    COMMAND_AFTERCOOKINGTIMERMANUAL,
    COMMAND_AFTERCOOKINGTIMEROFF,
    COMMAND_STOP_FAN,
    State,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import async_setup_entry_platform
from .coordinator import FjaraskupanCoordinator

ORDERED_NAMED_FAN_SPEEDS = ["1", "2", "3", "4", "5", "6", "7", "8"]

PRESET_MODE_NORMAL = "normal"
PRESET_MODE_AFTER_COOKING_MANUAL = "after_cooking_manual"
PRESET_MODE_AFTER_COOKING_AUTO = "after_cooking_auto"
PRESET_MODES = [
    PRESET_MODE_NORMAL,
    PRESET_MODE_AFTER_COOKING_AUTO,
    PRESET_MODE_AFTER_COOKING_MANUAL,
]

PRESET_TO_COMMAND = {
    PRESET_MODE_AFTER_COOKING_MANUAL: COMMAND_AFTERCOOKINGTIMERMANUAL,
    PRESET_MODE_AFTER_COOKING_AUTO: COMMAND_AFTERCOOKINGTIMERAUTO,
    PRESET_MODE_NORMAL: COMMAND_AFTERCOOKINGTIMEROFF,
}


class UnsupportedPreset(HomeAssistantError):
    """The preset is unsupported."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(coordinator: FjaraskupanCoordinator):
        return [Fan(coordinator, coordinator.device_info)]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class Fan(CoordinatorEntity[FjaraskupanCoordinator], FanEntity):
    """Fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: FjaraskupanCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Init fan entity."""
        super().__init__(coordinator)
        self._default_on_speed = 25
        self._attr_unique_id = coordinator.device.address
        self._attr_device_info = device_info
        self._percentage = 0
        self._preset_mode = PRESET_MODE_NORMAL
        self._update_from_device_data(coordinator.data)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed."""

        # Proactively update percentage to manage successive increases
        self._percentage = percentage

        async with self.coordinator.async_connect_and_update() as device:
            if percentage == 0:
                await device.send_command(COMMAND_STOP_FAN)
            else:
                new_speed = percentage_to_ordered_list_item(
                    ORDERED_NAMED_FAN_SPEEDS, percentage
                )
                await device.send_fan_speed(int(new_speed))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""

        if preset_mode is None:
            preset_mode = self._preset_mode

        if percentage is None:
            percentage = self._default_on_speed

        new_speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )

        async with self.coordinator.async_connect_and_update() as device:
            if preset_mode != self._preset_mode:
                if command := PRESET_TO_COMMAND.get(preset_mode):
                    await device.send_command(command)
                else:
                    raise UnsupportedPreset(f"The preset {preset_mode} is unsupported")

            if preset_mode == PRESET_MODE_NORMAL:
                await device.send_fan_speed(int(new_speed))
            elif preset_mode == PRESET_MODE_AFTER_COOKING_MANUAL:
                await device.send_after_cooking(int(new_speed))
            elif preset_mode == PRESET_MODE_AFTER_COOKING_AUTO:
                await device.send_after_cooking(0)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        command = PRESET_TO_COMMAND[preset_mode]
        async with self.coordinator.async_connect_and_update() as device:
            await device.send_command(command)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        async with self.coordinator.async_connect_and_update() as device:
            await device.send_command(COMMAND_STOP_FAN)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return self._percentage

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._percentage != 0

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return PRESET_MODES

    def _update_from_device_data(self, data: State | None) -> None:
        """Handle data update."""
        if not data:
            self._percentage = 0
            return

        if data.fan_speed:
            self._percentage = ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, str(data.fan_speed)
            )
        else:
            self._percentage = 0

        if data.after_cooking_on:
            if data.after_cooking_fan_speed:
                self._preset_mode = PRESET_MODE_AFTER_COOKING_MANUAL
            else:
                self._preset_mode = PRESET_MODE_AFTER_COOKING_AUTO
        else:
            self._preset_mode = PRESET_MODE_NORMAL

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""

        self._update_from_device_data(self.coordinator.data)
        self.async_write_ha_state()
