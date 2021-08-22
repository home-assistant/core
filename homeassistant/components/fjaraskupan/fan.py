"""Support for Fjäråskupan fans."""
from __future__ import annotations

from fjaraskupan import (
    COMMAND_AFTERCOOKINGTIMERAUTO,
    COMMAND_AFTERCOOKINGTIMERMANUAL,
    COMMAND_AFTERCOOKINGTIMEROFF,
    COMMAND_STOP_FAN,
    Device,
    State,
)

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import DeviceState, async_setup_entry_platform

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(device_state: DeviceState):
        return [
            Fan(device_state.coordinator, device_state.device, device_state.device_info)
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class Fan(CoordinatorEntity[State], FanEntity):
    """Fan entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init fan entity."""
        super().__init__(coordinator)
        self._device = device
        self._default_on_speed = 25
        self._attr_name = device_info["name"]
        self._attr_unique_id = device.address
        self._attr_device_info = device_info
        self._percentage = 0
        self._preset_mode = PRESET_MODE_NORMAL
        self._update_from_device_data(coordinator.data)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed."""
        new_speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )
        await self._device.send_fan_speed(int(new_speed))
        self.coordinator.async_set_updated_data(self._device.state)

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""

        if preset_mode is None:
            preset_mode = self._preset_mode

        if percentage is None:
            percentage = self._default_on_speed

        new_speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )

        async with self._device:
            if preset_mode != self._preset_mode:
                await self._device.send_command(PRESET_TO_COMMAND[preset_mode])

            if preset_mode == PRESET_MODE_NORMAL:
                await self._device.send_fan_speed(int(new_speed))
            elif preset_mode == PRESET_MODE_AFTER_COOKING_MANUAL:
                await self._device.send_after_cooking(int(new_speed))
            elif preset_mode == PRESET_MODE_AFTER_COOKING_AUTO:
                await self._device.send_after_cooking(0)

        self.coordinator.async_set_updated_data(self._device.state)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self._device.send_command(PRESET_TO_COMMAND[preset_mode])
        self.coordinator.async_set_updated_data(self._device.state)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._device.send_command(COMMAND_STOP_FAN)
        self.coordinator.async_set_updated_data(self._device.state)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return self._percentage

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE

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
