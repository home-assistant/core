"""Support for Tuya Cover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_device_handlers.device_wrapper.base import DeviceWrapper
from tuya_device_handlers.device_wrapper.cover import (
    ControlBackModePercentageMappingWrapper,
    CoverClosedEnumWrapper,
    CoverInstructionBooleanWrapper,
    CoverInstructionEnumWrapper,
    CoverInstructionSpecialEnumWrapper,
)
from tuya_device_handlers.device_wrapper.extended import (
    DPCodeInvertedBooleanWrapper,
    DPCodeInvertedPercentageWrapper,
    DPCodePercentageWrapper,
)
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


@dataclass(frozen=True)
class TuyaCoverEntityDescription(CoverEntityDescription):
    """Describe a Tuya cover entity."""

    current_state: DPCode | tuple[DPCode, ...] | None = None
    current_state_wrapper: type[
        DPCodeInvertedBooleanWrapper | CoverClosedEnumWrapper
    ] = CoverClosedEnumWrapper
    current_position: DPCode | tuple[DPCode, ...] | None = None
    instruction_wrapper: type[CoverInstructionEnumWrapper] = CoverInstructionEnumWrapper
    position_wrapper: type[DPCodePercentageWrapper] = DPCodeInvertedPercentageWrapper
    set_position: DPCode | None = None


COVERS: dict[DeviceCategory, tuple[TuyaCoverEntityDescription, ...]] = {
    DeviceCategory.CKMKZQ: (
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_door",
            translation_placeholders={"index": "1"},
            current_state=DPCode.DOORCONTACT_STATE,
            current_state_wrapper=DPCodeInvertedBooleanWrapper,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_door",
            translation_placeholders={"index": "2"},
            current_state=DPCode.DOORCONTACT_STATE_2,
            current_state_wrapper=DPCodeInvertedBooleanWrapper,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_door",
            translation_placeholders={"index": "3"},
            current_state=DPCode.DOORCONTACT_STATE_3,
            current_state_wrapper=DPCodeInvertedBooleanWrapper,
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
            instruction_wrapper=CoverInstructionSpecialEnumWrapper,
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
            position_wrapper=ControlBackModePercentageMappingWrapper,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            translation_key="indexed_curtain",
            translation_placeholders={"index": "2"},
            current_position=DPCode.PERCENT_CONTROL_2,
            position_wrapper=ControlBackModePercentageMappingWrapper,
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
) -> DeviceWrapper | None:
    """Get the instruction wrapper for the cover entity."""
    if enum_wrapper := description.instruction_wrapper.find_dpcode(
        device, description.key, prefer_function=True
    ):
        return enum_wrapper

    # Fallback to a boolean wrapper if available
    return CoverInstructionBooleanWrapper.find_dpcode(
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
                        current_state_wrapper=description.current_state_wrapper.find_dpcode(
                            device, description.current_state
                        ),
                        instruction_wrapper=_get_instruction_wrapper(
                            device, description
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
        current_position: DeviceWrapper[int] | None,
        current_state_wrapper: DeviceWrapper[bool] | None,
        instruction_wrapper: DeviceWrapper[str] | None,
        set_position: DeviceWrapper[int] | None,
        tilt_position: DeviceWrapper[int] | None,
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
            if "open" in instruction_wrapper.options:
                self._attr_supported_features |= CoverEntityFeature.OPEN
            if "close" in instruction_wrapper.options:
                self._attr_supported_features |= CoverEntityFeature.CLOSE
            if "stop" in instruction_wrapper.options:
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

        return self._read_wrapper(self._current_state_wrapper)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._set_position is not None:
            await self._async_send_commands(
                self._set_position.get_update_commands(self.device, 100)
            )
            return

        if (
            self._instruction_wrapper
            and (options := self._instruction_wrapper.options)
            and "open" in options
        ):
            await self._async_send_wrapper_updates(self._instruction_wrapper, "open")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if self._set_position is not None:
            await self._async_send_commands(
                self._set_position.get_update_commands(self.device, 0)
            )
            return

        if (
            self._instruction_wrapper
            and (options := self._instruction_wrapper.options)
            and "close" in options
        ):
            await self._async_send_wrapper_updates(self._instruction_wrapper, "close")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self._async_send_wrapper_updates(
            self._set_position, kwargs[ATTR_POSITION]
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._instruction_wrapper and "stop" in self._instruction_wrapper.options:
            await self._async_send_wrapper_updates(self._instruction_wrapper, "stop")

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self._async_send_wrapper_updates(
            self._tilt_position, kwargs[ATTR_TILT_POSITION]
        )
