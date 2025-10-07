"""Support for Tuya Cover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode, DPType
from .entity import TuyaEntity
from .models import EnumTypeData, IntegerTypeData
from .util import get_dpcode
from .xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY, parse_enum
from .xternal_tuya_quirks.cover import CommonCoverType, TuyaCoverDefinition


@dataclass(frozen=True)
class TuyaCoverEntityDescription(CoverEntityDescription):
    """Describe an Tuya cover entity."""

    current_state: DPCode | tuple[DPCode, ...] | None = None
    current_state_inverse: bool = False
    current_position: DPCode | tuple[DPCode, ...] | None = None
    set_position: DPCode | None = None
    open_instruction_value: str = "open"
    close_instruction_value: str = "close"
    stop_instruction_value: str = "stop"
    motor_reverse_mode: DPCode | None = None


COVERS: dict[DeviceCategory, tuple[TuyaCoverEntityDescription, ...]] = {
    DeviceCategory.CKMKZQ: (
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_door",
            translation_placeholders={"index": "1"},
            current_state=DPCode.DOORCONTACT_STATE,
            current_state_inverse=True,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_door",
            translation_placeholders={"index": "2"},
            current_state=DPCode.DOORCONTACT_STATE_2,
            current_state_inverse=True,
            device_class=CoverDeviceClass.GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_door",
            translation_placeholders={"index": "3"},
            current_state=DPCode.DOORCONTACT_STATE_3,
            current_state_inverse=True,
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
            open_instruction_value="FZ",
            close_instruction_value="ZZ",
            stop_instruction_value="STOP",
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
            set_position=DPCode.PERCENT_CONTROL,
            motor_reverse_mode=DPCode.CONTROL_BACK_MODE,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            translation_key="indexed_curtain",
            translation_placeholders={"index": "2"},
            current_position=DPCode.PERCENT_CONTROL_2,
            set_position=DPCode.PERCENT_CONTROL_2,
            motor_reverse_mode=DPCode.CONTROL_BACK_MODE,
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

COMMON_COVER_DEFINITIONS: dict[CommonCoverType, TuyaCoverEntityDescription] = {
    CommonCoverType.CURTAIN: TuyaCoverEntityDescription(
        key="tbc",
        translation_key="curtain",
        device_class=CoverDeviceClass.CURTAIN,
    )
}


def _create_quirk_description(
    definition: TuyaCoverDefinition,
) -> TuyaCoverEntityDescription:
    common_definition = COMMON_COVER_DEFINITIONS[definition.cover_type]
    return TuyaCoverEntityDescription(
        key=definition.key,
        device_class=common_definition.device_class,
        translation_key=common_definition.translation_key,
        current_state=parse_enum(DPCode, definition.current_state_dp_code),
        current_position=parse_enum(DPCode, definition.current_position_dp_code),
        set_position=parse_enum(DPCode, definition.set_position_dp_code),
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
            if quirk := TUYA_QUIRKS_REGISTRY.get_quirk_for_device(device):
                entities.extend(
                    TuyaCoverEntity(
                        device, manager, _create_quirk_description(definition)
                    )
                    for definition in quirk.cover_definitions
                    if (
                        definition.key in device.function
                        or definition.key in device.status_range
                    )
                )
            elif descriptions := COVERS.get(device.category):
                entities.extend(
                    TuyaCoverEntity(device, manager, description)
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

    _current_position: IntegerTypeData | None = None
    _current_state: DPCode | None = None
    _set_position: IntegerTypeData | None = None
    _tilt: IntegerTypeData | None = None
    _motor_reverse_mode_enum: EnumTypeData | None = None
    entity_description: TuyaCoverEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaCoverEntityDescription,
    ) -> None:
        """Init Tuya Cover."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_supported_features = CoverEntityFeature(0)

        # Check if this cover is based on a switch or has controls
        if get_dpcode(self.device, description.key):
            if device.function[description.key].type == "Boolean":
                self._attr_supported_features |= (
                    CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
                )
            elif enum_type := self.find_dpcode(
                description.key, dptype=DPType.ENUM, prefer_function=True
            ):
                if description.open_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.OPEN
                if description.close_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.CLOSE
                if description.stop_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.STOP

        self._current_state = get_dpcode(self.device, description.current_state)

        # Determine type to use for setting the position
        if int_type := self.find_dpcode(
            description.set_position, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
            self._set_position = int_type
            # Set as default, unless overwritten below
            self._current_position = int_type

        # Determine type for getting the position
        if int_type := self.find_dpcode(
            description.current_position, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._current_position = int_type

        # Determine type to use for setting the tilt
        if int_type := self.find_dpcode(
            (DPCode.ANGLE_HORIZONTAL, DPCode.ANGLE_VERTICAL),
            dptype=DPType.INTEGER,
            prefer_function=True,
        ):
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
            self._tilt = int_type

        # Determine type to use for checking motor reverse mode
        if (motor_mode := description.motor_reverse_mode) and (
            enum_type := self.find_dpcode(
                motor_mode,
                dptype=DPType.ENUM,
                prefer_function=True,
            )
        ):
            self._motor_reverse_mode_enum = enum_type

    @property
    def _is_position_reversed(self) -> bool:
        """Check if the cover position and direction should be reversed."""
        # The default is True
        # Having motor_reverse_mode == "back" cancels the inversion
        return not (
            self._motor_reverse_mode_enum
            and self.device.status.get(self._motor_reverse_mode_enum.dpcode) == "back"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return cover current position."""
        if self._current_position is None:
            return None

        if (position := self.device.status.get(self._current_position.dpcode)) is None:
            return None

        return round(
            self._current_position.remap_value_to(
                position, 0, 100, reverse=self._is_position_reversed
            )
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._tilt is None:
            return None

        if (angle := self.device.status.get(self._tilt.dpcode)) is None:
            return None

        return round(self._tilt.remap_value_to(angle, 0, 100))

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        # If it's available, prefer the position over the current state
        if (position := self.current_cover_position) is not None:
            return position == 0

        if (
            self._current_state is not None
            and (current_state := self.device.status.get(self._current_state))
            is not None
            and current_state != "stop"
        ):
            return self.entity_description.current_state_inverse is not (
                current_state in (True, "close", "fully_close")
            )

        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        value: bool | str = True
        if self.find_dpcode(
            self.entity_description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.open_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            100, 0, 100, reverse=self._is_position_reversed
                        ),
                    ),
                }
            )

        self._send_command(commands)

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        value: bool | str = False
        if self.find_dpcode(
            self.entity_description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.close_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            0, 0, 100, reverse=self._is_position_reversed
                        ),
                    ),
                }
            )

        self._send_command(commands)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if TYPE_CHECKING:
            # guarded by CoverEntityFeature.SET_POSITION
            assert self._set_position is not None

        self._send_command(
            [
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            kwargs[ATTR_POSITION],
                            0,
                            100,
                            reverse=self._is_position_reversed,
                        )
                    ),
                }
            ]
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self.entity_description.stop_instruction_value,
                }
            ]
        )

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if TYPE_CHECKING:
            # guarded by CoverEntityFeature.SET_TILT_POSITION
            assert self._tilt is not None

        self._send_command(
            [
                {
                    "code": self._tilt.dpcode,
                    "value": round(
                        self._tilt.remap_value_from(
                            kwargs[ATTR_TILT_POSITION],
                            0,
                            100,
                            reverse=self._is_position_reversed,
                        )
                    ),
                }
            ]
        )
