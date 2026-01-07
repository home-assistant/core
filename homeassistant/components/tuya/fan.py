"""Support for Tuya Fan."""

from __future__ import annotations

from typing import Any

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
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBooleanWrapper, DPCodeEnumWrapper, DPCodeIntegerWrapper
from .type_information import IntegerTypeInformation
from .util import RemapHelper, get_dpcode

_DIRECTION_DPCODES = (DPCode.FAN_DIRECTION,)
_MODE_DPCODES = (DPCode.FAN_MODE, DPCode.MODE)
_OSCILLATE_DPCODES = (DPCode.SWITCH_HORIZONTAL, DPCode.SWITCH_VERTICAL)
_SPEED_DPCODES = (
    DPCode.FAN_SPEED_PERCENT,
    DPCode.FAN_SPEED,
    DPCode.SPEED,
    DPCode.FAN_SPEED_ENUM,
)
_SWITCH_DPCODES = (DPCode.SWITCH_FAN, DPCode.FAN_SWITCH, DPCode.SWITCH)

TUYA_SUPPORT_TYPE: set[DeviceCategory] = {
    DeviceCategory.CS,
    DeviceCategory.FS,
    DeviceCategory.FSD,
    DeviceCategory.FSKG,
    DeviceCategory.KJ,
    DeviceCategory.KS,
}


class _DirectionEnumWrapper(DPCodeEnumWrapper):
    """Wrapper for fan direction DP code."""

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read the device status and return the direction string."""
        if (value := super().read_device_status(device)) and value in {
            DIRECTION_FORWARD,
            DIRECTION_REVERSE,
        }:
            return value
        return None


def _has_a_valid_dpcode(device: CustomerDevice) -> bool:
    """Check if the device has at least one valid DP code."""
    properties_to_check: list[DPCode | tuple[DPCode, ...] | None] = [
        # Main control switch
        _SWITCH_DPCODES,
        # Other properties
        _SPEED_DPCODES,
        _OSCILLATE_DPCODES,
        _DIRECTION_DPCODES,
    ]
    return any(get_dpcode(device, code) for code in properties_to_check)


class _FanSpeedEnumWrapper(DPCodeEnumWrapper):
    """Wrapper for fan speed DP code (from an enum)."""

    def read_device_status(self, device: CustomerDevice) -> int | None:
        """Get the current speed as a percentage."""
        if (value := super().read_device_status(device)) is None:
            return None
        return ordered_list_item_to_percentage(self.options, value)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        return percentage_to_ordered_list_item(self.options, value)


class _FanSpeedIntegerWrapper(DPCodeIntegerWrapper):
    """Wrapper for fan speed DP code (from an integer)."""

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
        """Init DPCodeIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self._remap_helper = RemapHelper.from_type_information(type_information, 1, 100)

    def read_device_status(self, device: CustomerDevice) -> int | None:
        """Get the current speed as a percentage."""
        if (value := super().read_device_status(device)) is None:
            return None
        return round(self._remap_helper.remap_value_to(value))

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        return round(self._remap_helper.remap_value_from(value))


def _get_speed_wrapper(
    device: CustomerDevice,
) -> _FanSpeedEnumWrapper | _FanSpeedIntegerWrapper | None:
    """Get the speed wrapper for the device."""
    if int_wrapper := _FanSpeedIntegerWrapper.find_dpcode(
        device, _SPEED_DPCODES, prefer_function=True
    ):
        return int_wrapper
    return _FanSpeedEnumWrapper.find_dpcode(
        device, _SPEED_DPCODES, prefer_function=True
    )


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
            if device.category in TUYA_SUPPORT_TYPE and _has_a_valid_dpcode(device):
                entities.append(
                    TuyaFanEntity(
                        device,
                        manager,
                        direction_wrapper=_DirectionEnumWrapper.find_dpcode(
                            device, _DIRECTION_DPCODES, prefer_function=True
                        ),
                        mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, _MODE_DPCODES, prefer_function=True
                        ),
                        oscillate_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, _OSCILLATE_DPCODES, prefer_function=True
                        ),
                        speed_wrapper=_get_speed_wrapper(device),
                        switch_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, _SWITCH_DPCODES, prefer_function=True
                        ),
                    )
                )
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
        *,
        direction_wrapper: _DirectionEnumWrapper | None,
        mode_wrapper: DPCodeEnumWrapper | None,
        oscillate_wrapper: DPCodeBooleanWrapper | None,
        speed_wrapper: _FanSpeedEnumWrapper | _FanSpeedIntegerWrapper | None,
        switch_wrapper: DPCodeBooleanWrapper | None,
    ) -> None:
        """Init Tuya Fan Device."""
        super().__init__(device, device_manager)
        self._direction_wrapper = direction_wrapper
        self._mode_wrapper = mode_wrapper
        self._oscillate_wrapper = oscillate_wrapper
        self._speed_wrapper = speed_wrapper
        self._switch_wrapper = switch_wrapper

        if mode_wrapper:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = mode_wrapper.options

        if speed_wrapper:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            if speed_wrapper.options is not None:
                self._attr_speed_count = len(speed_wrapper.options)

        if oscillate_wrapper:
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

        if direction_wrapper:
            self._attr_supported_features |= FanEntityFeature.DIRECTION
        if switch_wrapper:
            self._attr_supported_features |= (
                FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._async_send_wrapper_updates(self._mode_wrapper, preset_mode)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self._async_send_wrapper_updates(self._direction_wrapper, direction)

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
        return self._read_wrapper(self._direction_wrapper)

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
