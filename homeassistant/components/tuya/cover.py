"""Support for Tuya Cover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBooleanWrapper, DPCodeEnumWrapper, DPCodeIntegerWrapper


class _DPCodePercentageMappingWrapper(DPCodeIntegerWrapper):
    """Wrapper for DPCode position values mapping to 0-100 range."""

    def _position_reversed(self, device: CustomerDevice) -> bool:
        """Check if the position and direction should be reversed."""
        return False

    def read_device_status(self, device: CustomerDevice) -> float | None:
        if (value := self._read_device_status_raw(device)) is None:
            return None

        return round(
            self.type_information.remap_value_to(
                value,
                0,
                100,
                self._position_reversed(device),
            )
        )

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        return round(
            self.type_information.remap_value_from(
                value,
                0,
                100,
                self._position_reversed(device),
            )
        )


class _InvertedPercentageMappingWrapper(_DPCodePercentageMappingWrapper):
    """Wrapper for DPCode position values mapping to 0-100 range."""

    def _position_reversed(self, device: CustomerDevice) -> bool:
        """Check if the position and direction should be reversed."""
        return True


class _ControlBackModePercentageMappingWrapper(_DPCodePercentageMappingWrapper):
    """Wrapper for DPCode position values with control_back_mode support."""

    def _position_reversed(self, device: CustomerDevice) -> bool:
        """Check if the position and direction should be reversed."""
        return device.status.get(DPCode.CONTROL_BACK_MODE) != "back"


class _InstructionWrapper:
    """Default wrapper for sending open/close/stop instructions."""

    def get_open_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        return None

    def get_close_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        return None

    def get_stop_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        return None


class _InstructionBooleanWrapper(DPCodeBooleanWrapper, _InstructionWrapper):
    """Wrapper for boolean-based open/close instructions."""

    def get_open_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        return {"code": self.dpcode, "value": True}

    def get_close_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        return {"code": self.dpcode, "value": False}


class _InstructionEnumWrapper(DPCodeEnumWrapper, _InstructionWrapper):
    """Wrapper for enum-based open/close/stop instructions."""

    open_instruction = "open"
    close_instruction = "close"
    stop_instruction = "stop"

    def get_open_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        if self.open_instruction in self.type_information.range:
            return {"code": self.dpcode, "value": self.open_instruction}
        return None

    def get_close_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        if self.close_instruction in self.type_information.range:
            return {"code": self.dpcode, "value": self.close_instruction}
        return None

    def get_stop_command(self, device: CustomerDevice) -> dict[str, Any] | None:
        if self.stop_instruction in self.type_information.range:
            return {"code": self.dpcode, "value": self.stop_instruction}
        return None


class _SpecialInstructionEnumWrapper(_InstructionEnumWrapper):
    """Wrapper for enum-based instructions with special values (FZ/ZZ/STOP)."""

    open_instruction = "FZ"
    close_instruction = "ZZ"
    stop_instruction = "STOP"


class _IsClosedWrapper:
    """Wrapper for checking if cover is closed."""

    def is_closed(self, device: CustomerDevice) -> bool | None:
        return None


class _IsClosedInvertedWrapper(DPCodeBooleanWrapper, _IsClosedWrapper):
    """Boolean wrapper for checking if cover is closed (inverted)."""

    def is_closed(self, device: CustomerDevice) -> bool | None:
        if (value := self.read_device_status(device)) is None:
            return None
        return not value


class _IsClosedEnumWrapper(DPCodeEnumWrapper, _IsClosedWrapper):
    """Enum wrapper for checking if state is closed."""

    _MAPPINGS = {
        "close": True,
        "fully_close": True,
        "open": False,
        "fully_open": False,
    }

    def is_closed(self, device: CustomerDevice) -> bool | None:
        if (value := self.read_device_status(device)) is None:
            return None
        return self._MAPPINGS.get(value)


@dataclass(frozen=True)
class TuyaCoverEntityDescription(CoverEntityDescription):
    """Describe an Tuya cover entity."""

    current_state: DPCode | tuple[DPCode, ...] | None = None
    current_state_wrapper: type[_IsClosedInvertedWrapper | _IsClosedEnumWrapper] = (
        _IsClosedEnumWrapper
    )
    current_position: DPCode | tuple[DPCode, ...] | None = None
    instruction_wrapper: type[_InstructionEnumWrapper] = _InstructionEnumWrapper
    position_wrapper: type[_DPCodePercentageMappingWrapper] = (
        _InvertedPercentageMappingWrapper
    )
    set_position: DPCode | None = None


COVERS: dict[DeviceCategory, tuple[TuyaCoverEntityDescription, ...]] = {
    DeviceCategory.CKMKZQ: (
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_door",
            translation_placeholders={"index": "1"},
            current_state=DPCode.DOORCONTACT_STATE,
            current_state_wrapper=_IsClosedInvertedWrapper,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_door",
            translation_placeholders={"index": "2"},
            current_state=DPCode.DOORCONTACT_STATE_2,
            current_state_wrapper=_IsClosedInvertedWrapper,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_door",
            translation_placeholders={"index": "3"},
            current_state=DPCode.DOORCONTACT_STATE_3,
            current_state_wrapper=_IsClosedInvertedWrapper,
            device_class=CoverDeviceClass.GARAGE,
        ),
    ),
    DeviceCategory.CL: (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            translation_key="curtain",
            current_state=(DPCode.SITUATION_SET, DPCode.CONTROL),
            current_position=(DPCode.PERCENT_STATE, DPCode.PERCENT_CONTROL),
            set_position=DPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            translation_key="indexed_curtain",
            translation_placeholders={"index": "2"},
            current_position=DPCode.PERCENT_STATE_2,
            set_position=DPCode.PERCENT_CONTROL_2,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_3,
            translation_key="indexed_curtain",
            translation_placeholders={"index": "3"},
            current_position=DPCode.PERCENT_STATE_3,
            set_position=DPCode.PERCENT_CONTROL_3,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.MACH_OPERATE,
            translation_key="curtain",
            current_position=DPCode.POSITION,
            set_position=DPCode.POSITION,
            device_class=CoverDeviceClass.CURTAIN,
            instruction_wrapper=_SpecialInstructionEnumWrapper,
        ),
        # switch_1 is an undocumented code that behaves identically to control
        # It is used by the Kogan Smart Blinds Driver
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="blind",
            current_position=DPCode.PERCENT_CONTROL,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.BLIND,
        ),
    ),
    DeviceCategory.CLKG: (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            translation_key="curtain",
            current_position=DPCode.PERCENT_CONTROL,
            position_wrapper=_ControlBackModePercentageMappingWrapper,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            translation_key="indexed_curtain",
            translation_placeholders={"index": "2"},
            current_position=DPCode.PERCENT_CONTROL_2,
            position_wrapper=_ControlBackModePercentageMappingWrapper,
            set_position=DPCode.PERCENT_CONTROL_2,
            device_class=CoverDeviceClass.CURTAIN,
        ),
    ),
    DeviceCategory.JDCLJQR: (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            translation_key="curtain",
            current_position=DPCode.PERCENT_STATE,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
        ),
    ),
}


def _get_instruction_wrapper(
    device: CustomerDevice, description: TuyaCoverEntityDescription
) -> _InstructionWrapper | None:
    """Get the instruction wrapper for the cover entity."""
    if enum_wrapper := description.instruction_wrapper.find_dpcode(
        device, description.key, prefer_function=True
    ):
        return enum_wrapper

    # Fallback to a boolean wrapper if available
    return _InstructionBooleanWrapper.find_dpcode(
        device, description.key, prefer_function=True
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya cover."""
        entities: list[TuyaCoverEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := COVERS.get(device.category):
                entities.extend(
                    TuyaCoverEntity(
                        device,
                        manager,
                        description,
                        current_position=description.position_wrapper.find_dpcode(
                            device, description.current_position
                        ),
                        instruction_wrapper=_get_instruction_wrapper(
                            device, description
                        ),
                        current_state_wrapper=description.current_state_wrapper.find_dpcode(
                            device, description.current_state
                        ),
                        set_position=description.position_wrapper.find_dpcode(
                            device, description.set_position, prefer_function=True
                        ),
                        tilt_position=description.position_wrapper.find_dpcode(
                            device,
                            (DPCode.ANGLE_HORIZONTAL, DPCode.ANGLE_VERTICAL),
                            prefer_function=True,
                        ),
                    )
                    for description in descriptions
                    if (
                        description.key in device.function
                        or description.key in device.status_range
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaCoverEntity(TuyaEntity, CoverEntity):
    """Tuya Cover Device."""

    entity_description: TuyaCoverEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaCoverEntityDescription,
        *,
        current_position: _DPCodePercentageMappingWrapper | None,
        current_state_wrapper: _IsClosedWrapper | None,
        instruction_wrapper: _InstructionWrapper | None,
        set_position: _DPCodePercentageMappingWrapper | None,
        tilt_position: _DPCodePercentageMappingWrapper | None,
    ) -> None:
        """Init Tuya Cover."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_supported_features = CoverEntityFeature(0)

        self._current_position = current_position or set_position
        self._current_state_wrapper = current_state_wrapper
        self._instruction_wrapper = instruction_wrapper
        self._set_position = set_position
        self._tilt_position = tilt_position

        if instruction_wrapper:
            if instruction_wrapper.get_open_command(device) is not None:
                self._attr_supported_features |= CoverEntityFeature.OPEN
            if instruction_wrapper.get_close_command(device) is not None:
                self._attr_supported_features |= CoverEntityFeature.CLOSE
            if instruction_wrapper.get_stop_command(device) is not None:
                self._attr_supported_features |= CoverEntityFeature.STOP

        if set_position:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        if tilt_position:
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION

    @property
    def current_cover_position(self) -> int | None:
        """Return cover current position."""
        return self._read_wrapper(self._current_position)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._read_wrapper(self._tilt_position)

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        # If it's available, prefer the position over the current state
        if (position := self.current_cover_position) is not None:
            return position == 0

        if self._current_state_wrapper:
            return self._current_state_wrapper.is_closed(self.device)

        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._instruction_wrapper and (
            command := self._instruction_wrapper.get_open_command(self.device)
        ):
            await self._async_send_commands([command])
            return

        if self._set_position is not None:
            await self._async_send_commands(
                [self._set_position.get_update_command(self.device, 100)]
            )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if self._instruction_wrapper and (
            command := self._instruction_wrapper.get_close_command(self.device)
        ):
            await self._async_send_commands([command])
            return

        if self._set_position is not None:
            await self._async_send_commands(
                [self._set_position.get_update_command(self.device, 0)]
            )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._async_send_dpcode_update(self._set_position, kwargs[ATTR_POSITION])

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._instruction_wrapper and (
            command := self._instruction_wrapper.get_stop_command(self.device)
        ):
            await self._async_send_commands([command])

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self._async_send_dpcode_update(
            self._tilt_position, kwargs[ATTR_TILT_POSITION]
        )
