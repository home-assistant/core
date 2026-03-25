"""Support for Tuya Fan."""

from __future__ import annotations

from typing import Any

from tuya_device_handlers.definition.fan import (
    TuyaFanDefinition,
    get_default_definition,
)
from tuya_device_handlers.helpers.homeassistant import TuyaFanDirection
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory
from .entity import TuyaEntity

TUYA_SUPPORT_TYPE: set[DeviceCategory] = {
    DeviceCategory.CS,
    DeviceCategory.FS,
    DeviceCategory.FSD,
    DeviceCategory.FSKG,
    DeviceCategory.KJ,
    DeviceCategory.KS,
}

_TUYA_TO_HA_DIRECTION_MAPPINGS = {
    TuyaFanDirection.FORWARD: DIRECTION_FORWARD,
    TuyaFanDirection.REVERSE: DIRECTION_REVERSE,
}
_HA_TO_TUYA_DIRECTION_MAPPINGS = {
    v: k for k, v in _TUYA_TO_HA_DIRECTION_MAPPINGS.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tuya fan dynamically through tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya fan."""
        entities: list[TuyaFanEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if device.category in TUYA_SUPPORT_TYPE and (
                definition := get_default_definition(device)
            ):
                entities.append(TuyaFanEntity(device, manager, definition))
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaFanEntity(TuyaEntity, FanEntity):
    """Tuya Fan Device."""

    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        definition: TuyaFanDefinition,
    ) -> None:
        """Init Tuya Fan Device."""
        super().__init__(device, device_manager)
        self._direction_wrapper = definition.direction_wrapper
        self._mode_wrapper = definition.mode_wrapper
        self._oscillate_wrapper = definition.oscillate_wrapper
        self._speed_wrapper = definition.speed_wrapper
        self._switch_wrapper = definition.switch_wrapper

        if definition.mode_wrapper:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = definition.mode_wrapper.options

        if definition.speed_wrapper:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            # if speed is from an enum, set speed count from options
            # else keep entity default 100
            if hasattr(definition.speed_wrapper, "options"):
                self._attr_speed_count = len(definition.speed_wrapper.options)

        if definition.oscillate_wrapper:
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

        if definition.direction_wrapper:
            self._attr_supported_features |= FanEntityFeature.DIRECTION
        if definition.switch_wrapper:
            self._attr_supported_features |= (
                FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._async_send_wrapper_updates(self._mode_wrapper, preset_mode)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if tuya_value := _HA_TO_TUYA_DIRECTION_MAPPINGS.get(direction):
            await self._async_send_wrapper_updates(self._direction_wrapper, tuya_value)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self._async_send_wrapper_updates(self._speed_wrapper, percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_send_wrapper_updates(self._switch_wrapper, False)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if self._switch_wrapper is None:
            return

        commands = self._switch_wrapper.get_update_commands(self.device, True)

        if percentage is not None and self._speed_wrapper is not None:
            commands.extend(
                self._speed_wrapper.get_update_commands(self.device, percentage)
            )

        if preset_mode is not None and self._mode_wrapper:
            commands.extend(
                self._mode_wrapper.get_update_commands(self.device, preset_mode)
            )
        await self._async_send_commands(commands)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._async_send_wrapper_updates(self._oscillate_wrapper, oscillating)

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        return self._read_wrapper(self._switch_wrapper)

    @property
    def current_direction(self) -> str | None:
        """Return the current direction of the fan."""
        tuya_value = self._read_wrapper(self._direction_wrapper)
        return _TUYA_TO_HA_DIRECTION_MAPPINGS.get(tuya_value) if tuya_value else None

    @property
    def oscillating(self) -> bool | None:
        """Return true if the fan is oscillating."""
        return self._read_wrapper(self._oscillate_wrapper)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset_mode."""
        return self._read_wrapper(self._mode_wrapper)

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        return self._read_wrapper(self._speed_wrapper)
