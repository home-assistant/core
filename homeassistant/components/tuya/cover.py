"""Support for Tuya Cover."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GARAGE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    CoverEntity,
    CoverEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuyaCoverEntityDescription(CoverEntityDescription):
    """Describe an Tuya cover entity."""

    current_state: DPCode | None = None
    current_state_inverse: bool = False
    current_position: DPCode | None = None
    set_position: DPCode | None = None


COVERS: dict[str, tuple[TuyaCoverEntityDescription, ...]] = {
    # Curtain
    # Note: Multiple curtains isn't documented
    # https://developer.tuya.com/en/docs/iot/categorycl?id=Kaiuz1hnpo7df
    "cl": (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            name="Curtain",
            current_state=DPCode.SITUATION_SET,
            current_position=DPCode.PERCENT_STATE,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            name="Curtain 2",
            current_position=DPCode.PERCENT_STATE_2,
            set_position=DPCode.PERCENT_CONTROL_2,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_3,
            name="Curtain 3",
            current_position=DPCode.PERCENT_STATE_3,
            set_position=DPCode.PERCENT_CONTROL_3,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
    ),
    # Garage Door Opener
    # https://developer.tuya.com/en/docs/iot/categoryckmkzq?id=Kaiuz0ipcboee
    "ckmkzq": (
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_1,
            name="Door",
            current_state=DPCode.DOORCONTACT_STATE,
            current_state_inverse=True,
            device_class=DEVICE_CLASS_GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_2,
            name="Door 2",
            current_state=DPCode.DOORCONTACT_STATE_2,
            current_state_inverse=True,
            device_class=DEVICE_CLASS_GARAGE,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.SWITCH_3,
            name="Door 3",
            current_state=DPCode.DOORCONTACT_STATE_3,
            current_state_inverse=True,
            device_class=DEVICE_CLASS_GARAGE,
        ),
    ),
    # Curtain Switch
    # https://developer.tuya.com/en/docs/iot/category-clkg?id=Kaiuz0gitil39
    "clkg": (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            name="Curtain",
            current_position=DPCode.PERCENT_CONTROL,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL_2,
            name="Curtain 2",
            current_position=DPCode.PERCENT_CONTROL_2,
            set_position=DPCode.PERCENT_CONTROL_2,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
    ),
    # Curtain Robot
    # Note: Not documented
    "jdcljqr": (
        TuyaCoverEntityDescription(
            key=DPCode.CONTROL,
            current_position=DPCode.PERCENT_STATE,
            set_position=DPCode.PERCENT_CONTROL,
            device_class=DEVICE_CLASS_CURTAIN,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya cover."""
        entities: list[TuyaCoverEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := COVERS.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaCoverEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaCoverEntity(TuyaEntity, CoverEntity):
    """Tuya Cover Device."""

    _current_position_type: IntegerTypeData | None = None
    _set_position_type: IntegerTypeData | None = None
    _tilt_dpcode: DPCode | None = None
    _tilt_type: IntegerTypeData | None = None
    entity_description: TuyaCoverEntityDescription

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaCoverEntityDescription,
    ) -> None:
        """Init Tuya Cover."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_supported_features = 0

        # Check if this cover is based on a switch or has controls
        if device.function[description.key].type == "Boolean":
            self._attr_supported_features |= SUPPORT_OPEN | SUPPORT_CLOSE
        elif device.function[description.key].type == "Enum":
            data_type = EnumTypeData.from_json(
                device.status_range[description.key].values
            )
            if "open" in data_type.range:
                self._attr_supported_features |= SUPPORT_OPEN
            if "close" in data_type.range:
                self._attr_supported_features |= SUPPORT_CLOSE
            if "stop" in data_type.range:
                self._attr_supported_features |= SUPPORT_STOP

        # Determine type to use for setting the position
        if (
            description.set_position is not None
            and description.set_position in device.status_range
        ):
            self._attr_supported_features |= SUPPORT_SET_POSITION
            self._set_position_type = IntegerTypeData.from_json(
                device.status_range[description.set_position].values
            )
            # Set as default, unless overwritten below
            self._current_position_type = self._set_position_type

        # Determine type for getting the position
        if (
            description.current_position is not None
            and description.current_position in device.status_range
        ):
            self._current_position_type = IntegerTypeData.from_json(
                device.status_range[description.current_position].values
            )

        # Determine type to use for setting the tilt
        if tilt_dpcode := next(
            (
                dpcode
                for dpcode in (DPCode.ANGLE_HORIZONTAL, DPCode.ANGLE_VERTICAL)
                if dpcode in device.function
            ),
            None,
        ):
            self._attr_supported_features |= SUPPORT_SET_TILT_POSITION
            self._tilt_dpcode = tilt_dpcode
            self._tilt_type = IntegerTypeData.from_json(
                device.status_range[tilt_dpcode].values
            )

    @property
    def current_cover_position(self) -> int | None:
        """Return cover current position."""
        if self._current_position_type is None:
            return None

        if not (
            dpcode := (
                self.entity_description.current_position
                or self.entity_description.set_position
            )
        ):
            return None

        if (position := self.device.status.get(dpcode)) is None:
            return None

        return round(
            self._current_position_type.remap_value_to(position, 0, 100, reverse=True)
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._tilt_dpcode is None or self._tilt_type is None:
            return None

        if (angle := self.device.status.get(self._tilt_dpcode)) is None:
            return None

        return round(self._tilt_type.remap_value_to(angle, 0, 100))

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if (
            self.entity_description.current_state is not None
            and (
                current_state := self.device.status.get(
                    self.entity_description.current_state
                )
            )
            is not None
        ):
            return self.entity_description.current_state_inverse is not (
                current_state in (False, "fully_close")
            )

        if (position := self.current_cover_position) is not None:
            return position == 0

        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        value: bool | str = True
        if self.device.function[self.entity_description.key].type == "Enum":
            value = "open"
        self._send_command([{"code": self.entity_description.key, "value": value}])

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        value: bool | str = True
        if self.device.function[self.entity_description.key].type == "Enum":
            value = "close"
        self._send_command([{"code": self.entity_description.key, "value": value}])

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if self._set_position_type is None:
            raise RuntimeError(
                "Cannot set position, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self.entity_description.set_position,
                    "value": round(
                        self._set_position_type.remap_value_from(
                            kwargs[ATTR_POSITION], 0, 100, reverse=True
                        )
                    ),
                }
            ]
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._send_command([{"code": self.entity_description.key, "value": "stop"}])

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if self._tilt_type is None:
            raise RuntimeError(
                "Cannot set tilt, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._tilt_dpcode,
                    "value": round(
                        self._tilt_type.remap_value_from(
                            kwargs[ATTR_TILT_POSITION], 0, 100, reverse=True
                        )
                    ),
                }
            ]
        )
