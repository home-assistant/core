"""Support for Cover devices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from enum import IntFlag, StrEnum
import functools as ft
from functools import cached_property
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, INTENT_CLOSE_COVER, INTENT_OPEN_COVER  # noqa: F401

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[CoverEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=15)


class CoverDeviceClass(StrEnum):
    """Device class for cover."""

    # Refer to the cover dev docs for device class descriptions
    AWNING = "awning"
    BLIND = "blind"
    CURTAIN = "curtain"
    DAMPER = "damper"
    DOOR = "door"
    GARAGE = "garage"
    GATE = "gate"
    SHADE = "shade"
    SHUTTER = "shutter"
    WINDOW = "window"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(CoverDeviceClass))

# DEVICE_CLASS* below are deprecated as of 2021.12
# use the CoverDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in CoverDeviceClass]
_DEPRECATED_DEVICE_CLASS_AWNING = DeprecatedConstantEnum(
    CoverDeviceClass.AWNING, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_BLIND = DeprecatedConstantEnum(
    CoverDeviceClass.BLIND, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_CURTAIN = DeprecatedConstantEnum(
    CoverDeviceClass.CURTAIN, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_DAMPER = DeprecatedConstantEnum(
    CoverDeviceClass.DAMPER, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_DOOR = DeprecatedConstantEnum(CoverDeviceClass.DOOR, "2025.1")
_DEPRECATED_DEVICE_CLASS_GARAGE = DeprecatedConstantEnum(
    CoverDeviceClass.GARAGE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_GATE = DeprecatedConstantEnum(CoverDeviceClass.GATE, "2025.1")
_DEPRECATED_DEVICE_CLASS_SHADE = DeprecatedConstantEnum(
    CoverDeviceClass.SHADE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_SHUTTER = DeprecatedConstantEnum(
    CoverDeviceClass.SHUTTER, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_WINDOW = DeprecatedConstantEnum(
    CoverDeviceClass.WINDOW, "2025.1"
)

# mypy: disallow-any-generics


class CoverEntityFeature(IntFlag):
    """Supported features of the cover entity."""

    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8
    OPEN_TILT = 16
    CLOSE_TILT = 32
    STOP_TILT = 64
    SET_TILT_POSITION = 128


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the CoverEntityFeature enum instead.
_DEPRECATED_SUPPORT_OPEN = DeprecatedConstantEnum(CoverEntityFeature.OPEN, "2025.1")
_DEPRECATED_SUPPORT_CLOSE = DeprecatedConstantEnum(CoverEntityFeature.CLOSE, "2025.1")
_DEPRECATED_SUPPORT_SET_POSITION = DeprecatedConstantEnum(
    CoverEntityFeature.SET_POSITION, "2025.1"
)
_DEPRECATED_SUPPORT_STOP = DeprecatedConstantEnum(CoverEntityFeature.STOP, "2025.1")
_DEPRECATED_SUPPORT_OPEN_TILT = DeprecatedConstantEnum(
    CoverEntityFeature.OPEN_TILT, "2025.1"
)
_DEPRECATED_SUPPORT_CLOSE_TILT = DeprecatedConstantEnum(
    CoverEntityFeature.CLOSE_TILT, "2025.1"
)
_DEPRECATED_SUPPORT_STOP_TILT = DeprecatedConstantEnum(
    CoverEntityFeature.STOP_TILT, "2025.1"
)
_DEPRECATED_SUPPORT_SET_TILT_POSITION = DeprecatedConstantEnum(
    CoverEntityFeature.SET_TILT_POSITION, "2025.1"
)

ATTR_CURRENT_POSITION = "current_position"
ATTR_CURRENT_TILT_POSITION = "current_tilt_position"
ATTR_POSITION = "position"
ATTR_TILT_POSITION = "tilt_position"


@bind_hass
def is_closed(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_CLOSED)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for covers."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[CoverEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_OPEN_COVER, None, "async_open_cover", [CoverEntityFeature.OPEN]
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER, None, "async_close_cover", [CoverEntityFeature.CLOSE]
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_cover_position",
        [CoverEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER, None, "async_stop_cover", [CoverEntityFeature.STOP]
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_OPEN_COVER_TILT,
        None,
        "async_open_cover_tilt",
        [CoverEntityFeature.OPEN_TILT],
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER_TILT,
        None,
        "async_close_cover_tilt",
        [CoverEntityFeature.CLOSE_TILT],
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER_TILT,
        None,
        "async_stop_cover_tilt",
        [CoverEntityFeature.STOP_TILT],
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_TILT_POSITION,
        {
            vol.Required(ATTR_TILT_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_cover_tilt_position",
        [CoverEntityFeature.SET_TILT_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE_COVER_TILT,
        None,
        "async_toggle_tilt",
        [CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class CoverEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes cover entities."""

    device_class: CoverDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "current_cover_position",
    "current_cover_tilt_position",
    "device_class",
    "is_opening",
    "is_closing",
    "is_closed",
}


class CoverEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for cover entities."""

    entity_description: CoverEntityDescription
    _attr_current_cover_position: int | None = None
    _attr_current_cover_tilt_position: int | None = None
    _attr_device_class: CoverDeviceClass | None
    _attr_is_closed: bool | None
    _attr_is_closing: bool | None = None
    _attr_is_opening: bool | None = None
    _attr_state: None = None
    _attr_supported_features: CoverEntityFeature | None

    _cover_is_last_toggle_direction_open = True

    @cached_property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_cover_position

    @cached_property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_cover_tilt_position

    @cached_property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the cover."""
        if self.is_opening:
            self._cover_is_last_toggle_direction_open = True
            return STATE_OPENING
        if self.is_closing:
            self._cover_is_last_toggle_direction_open = False
            return STATE_CLOSING

        if (closed := self.is_closed) is None:
            return None

        return STATE_CLOSED if closed else STATE_OPEN

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        data = {}

        if (current := self.current_cover_position) is not None:
            data[ATTR_CURRENT_POSITION] = current

        if (current_tilt := self.current_cover_tilt_position) is not None:
            data[ATTR_CURRENT_TILT_POSITION] = current_tilt

        return data

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        if (features := self._attr_supported_features) is not None:
            if type(features) is int:  # noqa: E721
                new_features = CoverEntityFeature(features)
                self._report_deprecated_supported_features_values(new_features)
                return new_features
            return features

        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

        if self.current_cover_position is not None:
            supported_features |= CoverEntityFeature.SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

        return supported_features

    @cached_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        return self._attr_is_opening

    @cached_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return self._attr_is_closing

    @cached_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._attr_is_closed

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        raise NotImplementedError

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.hass.async_add_executor_job(ft.partial(self.open_cover, **kwargs))

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        raise NotImplementedError

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.hass.async_add_executor_job(ft.partial(self.close_cover, **kwargs))

    def toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        fns = {
            "open": self.open_cover,
            "close": self.close_cover,
            "stop": self.stop_cover,
        }
        function = self._get_toggle_function(fns)
        function(**kwargs)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        fns = {
            "open": self.async_open_cover,
            "close": self.async_close_cover,
            "stop": self.async_stop_cover,
        }
        function = self._get_toggle_function(fns)
        await function(**kwargs)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_cover_position, **kwargs)
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.hass.async_add_executor_job(ft.partial(self.stop_cover, **kwargs))

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self.hass.async_add_executor_job(
            ft.partial(self.open_cover_tilt, **kwargs)
        )

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self.hass.async_add_executor_job(
            ft.partial(self.close_cover_tilt, **kwargs)
        )

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self.hass.async_add_executor_job(
            ft.partial(self.set_cover_tilt_position, **kwargs)
        )

    def stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.hass.async_add_executor_job(
            ft.partial(self.stop_cover_tilt, **kwargs)
        )

    def toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.current_cover_tilt_position == 0:
            self.open_cover_tilt(**kwargs)
        else:
            self.close_cover_tilt(**kwargs)

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.current_cover_tilt_position == 0:
            await self.async_open_cover_tilt(**kwargs)
        else:
            await self.async_close_cover_tilt(**kwargs)

    def _get_toggle_function[**_P, _R](
        self, fns: dict[str, Callable[_P, _R]]
    ) -> Callable[_P, _R]:
        # If we are opening or closing and we support stopping, then we should stop
        if self.supported_features & CoverEntityFeature.STOP and (
            self.is_closing or self.is_opening
        ):
            return fns["stop"]

        # If we are fully closed or in the process of closing, then we should open
        if self.is_closed or self.is_closing:
            return fns["open"]

        # If we are fully open or in the process of opening, then we should close
        if self.current_cover_position == 100 or self.is_opening:
            return fns["close"]

        # We are any of:
        # * fully open but do not report `current_cover_position`
        # * stopped partially open
        # * either opening or closing, but do not report them
        # If we previously reported opening/closing, we should move in the opposite direction.
        # Otherwise, we must assume we are (partially) open and should always close.
        # Note: _cover_is_last_toggle_direction_open will always remain True if we never report opening/closing.
        return (
            fns["close"] if self._cover_is_last_toggle_direction_open else fns["open"]
        )


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = ft.partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = ft.partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
