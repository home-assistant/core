"""Support for Cover devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import IntFlag, StrEnum
import functools as ft
import logging
from typing import Any, ParamSpec, TypeVar, final

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
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "cover"
SCAN_INTERVAL = timedelta(seconds=15)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_P = ParamSpec("_P")
_R = TypeVar("_R")


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
DEVICE_CLASS_AWNING = CoverDeviceClass.AWNING.value
DEVICE_CLASS_BLIND = CoverDeviceClass.BLIND.value
DEVICE_CLASS_CURTAIN = CoverDeviceClass.CURTAIN.value
DEVICE_CLASS_DAMPER = CoverDeviceClass.DAMPER.value
DEVICE_CLASS_DOOR = CoverDeviceClass.DOOR.value
DEVICE_CLASS_GARAGE = CoverDeviceClass.GARAGE.value
DEVICE_CLASS_GATE = CoverDeviceClass.GATE.value
DEVICE_CLASS_SHADE = CoverDeviceClass.SHADE.value
DEVICE_CLASS_SHUTTER = CoverDeviceClass.SHUTTER.value
DEVICE_CLASS_WINDOW = CoverDeviceClass.WINDOW.value

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
SUPPORT_OPEN = 1
SUPPORT_CLOSE = 2
SUPPORT_SET_POSITION = 4
SUPPORT_STOP = 8
SUPPORT_OPEN_TILT = 16
SUPPORT_CLOSE_TILT = 32
SUPPORT_STOP_TILT = 64
SUPPORT_SET_TILT_POSITION = 128

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
    component = hass.data[DOMAIN] = EntityComponent[CoverEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_OPEN_COVER, {}, "async_open_cover", [CoverEntityFeature.OPEN]
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER, {}, "async_close_cover", [CoverEntityFeature.CLOSE]
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
        SERVICE_STOP_COVER, {}, "async_stop_cover", [CoverEntityFeature.STOP]
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        {},
        "async_toggle",
        [CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_OPEN_COVER_TILT,
        {},
        "async_open_cover_tilt",
        [CoverEntityFeature.OPEN_TILT],
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER_TILT,
        {},
        "async_close_cover_tilt",
        [CoverEntityFeature.CLOSE_TILT],
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER_TILT,
        {},
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
        {},
        "async_toggle_tilt",
        [CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[CoverEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[CoverEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class CoverEntityDescription(EntityDescription):
    """A class that describes cover entities."""

    device_class: CoverDeviceClass | None = None


class CoverEntity(Entity):
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

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_cover_position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_cover_tilt_position

    @property
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

        _LOGGER.info(
            f"state: is_opening={self.is_opening}, is_closing={self.is_closing}, is_closed{self.is_closed}"
        )
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
        if self._attr_supported_features is not None:
            return self._attr_supported_features

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

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        return self._attr_is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return self._attr_is_closing

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._attr_is_closed

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        raise NotImplementedError()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.hass.async_add_executor_job(ft.partial(self.open_cover, **kwargs))

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        raise NotImplementedError()

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

    def _get_toggle_function(
        self, fns: dict[str, Callable[_P, _R]]
    ) -> Callable[_P, _R]:
        if CoverEntityFeature.STOP | self.supported_features and (
            self.is_closing or self.is_opening
        ):
            return fns["stop"]
        if self.is_closed:
            return fns["open"]
        if self._cover_is_last_toggle_direction_open:
            return fns["close"]
        return fns["open"]
