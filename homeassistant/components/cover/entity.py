"""Base entity for the Cover platform."""

from collections.abc import Callable
import functools as ft
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import Entity, EntityDescription

from .const import (
    CoverDeviceClass,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
    CoverServiceArgument,
    CoverState,
)


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
    "supported_speeds",
    "open_tilt_position",
    "closed_tilt_positions",
    "tilt_start_angle",
    "tilt_end_angle",
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
    _attr_supported_speeds: list[str] | None = None
    _attr_open_tilt_position: int | None = None
    _attr_closed_tilt_positions: list[int] | None = None
    _attr_tilt_start_angle: int | None = None
    _attr_tilt_end_angle: int | None = None

    _cover_is_last_toggle_direction_open = True

    _entity_component_unrecorded_attributes = frozenset(
        {
            CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS,
            CoverEntityCapabilityAttribute.OPEN_TILT_POSITION,
            CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS,
            CoverEntityCapabilityAttribute.TILT_START_ANGLE,
            CoverEntityCapabilityAttribute.TILT_END_ANGLE,
        }
    )

    @cached_property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_cover_position

    @cached_property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown. By default 0 is closed and 100 is fully open,
        open_tilt_position and closed_tilt_positions describe other covers.
        """
        return self._attr_current_cover_tilt_position

    @cached_property
    @override
    def device_class(self) -> CoverDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the state of the cover."""
        if self.is_opening:
            self._cover_is_last_toggle_direction_open = True
            return CoverState.OPENING
        if self.is_closing:
            self._cover_is_last_toggle_direction_open = False
            return CoverState.CLOSING

        if (closed := self.is_closed) is None:
            return None

        if closed:
            # A closed cover can only open next. Reset the toggle direction,
            # so a cover then opened outside Home Assistant, without reporting
            # opening, closes on the next toggle.
            self._cover_is_last_toggle_direction_open = True
            return CoverState.CLOSED

        return CoverState.OPEN

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        data: dict[str, Any] = {}

        data[CoverEntityStateAttribute.IS_CLOSED] = self.is_closed

        if (current := self.current_cover_position) is not None:
            data[CoverEntityStateAttribute.CURRENT_POSITION] = current

        if (current_tilt := self.current_cover_tilt_position) is not None:
            data[CoverEntityStateAttribute.CURRENT_TILT_POSITION] = current_tilt

        return data

    @property
    @override
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        if (features := self._attr_supported_features) is not None:
            return features

        supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

        if self.supported_speeds:
            supported_features |= CoverEntityFeature.SPEED

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

    @cached_property
    def supported_speeds(self) -> list[str] | None:
        """Return the list of speeds supported for open/close/set_position operations.

        None or an empty list means speed selection is not supported.
        """
        return self._attr_supported_speeds

    @cached_property
    def open_tilt_position(self) -> int | None:
        """Return the tilt position where the slats are open.

        open_cover_tilt moves the slats to this position. None means the
        default: the position where the angle is 0 degrees if the angles
        are set, 100 otherwise.
        """
        return self._attr_open_tilt_position

    @cached_property
    def closed_tilt_positions(self) -> list[int] | None:
        """Return the one or two tilt positions where the slats are closed.

        close_cover_tilt moves the slats to one of them. None means the
        default: the ends where the slats lie flat if the angles are set,
        0 otherwise.
        """
        return self._attr_closed_tilt_positions

    @cached_property
    def tilt_start_angle(self) -> int | None:
        """Return the angle of the slats at tilt 0, from -90 to 90 degrees."""
        return self._attr_tilt_start_angle

    @cached_property
    def tilt_end_angle(self) -> int | None:
        """Return the angle of the slats at tilt 100, from -90 to 90 degrees."""
        return self._attr_tilt_end_angle

    @final
    def _tilt_angles(self) -> tuple[int, int] | None:
        """Return the start and end angles of the tilt, if both are set."""
        start = self.tilt_start_angle
        end = self.tilt_end_angle
        if start is None or end is None or start == end:
            return None
        return start, end

    @final
    def _resolved_open_tilt_position(self) -> int:
        """Return the open tilt position, with the default applied."""
        if (position := self.open_tilt_position) is not None:
            return position
        if (angles := self._tilt_angles()) is None:
            return 100
        start, end = angles
        return min(max(round(-start * 100 / (end - start)), 0), 100)

    @final
    def _resolved_closed_tilt_positions(self) -> list[int]:
        """Return the closed tilt positions, with the default applied."""
        open_position = self._resolved_open_tilt_position()
        positions: set[int] = set()
        if (closed := self.closed_tilt_positions) is not None:
            positions = set(closed)
        elif (angles := self._tilt_angles()) is not None:
            # The ends where the slats lie the flattest, usually at 90 degrees
            flattest = max(abs(angle) for angle in angles)
            positions = {
                position
                for position, angle in zip((0, 100), angles, strict=True)
                if abs(angle) == flattest
            }
        positions.discard(open_position)
        if not positions:
            return [100 if open_position == 0 else 0]
        return sorted(positions)[:2]

    @final
    def _is_tilt_closed(self) -> bool:
        """Return if the tilt is at a position where the slats are closed."""
        return (
            self.current_cover_tilt_position in self._resolved_closed_tilt_positions()
        )

    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        data: dict[str, Any] = {}

        if speeds := self.supported_speeds:
            data[CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS] = speeds

        if self.supported_features & CoverEntityFeature.SET_TILT_POSITION:
            data[CoverEntityCapabilityAttribute.OPEN_TILT_POSITION] = (
                self._resolved_open_tilt_position()
            )
            data[CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS] = (
                self._resolved_closed_tilt_positions()
            )
            if (angles := self._tilt_angles()) is not None:
                data[CoverEntityCapabilityAttribute.TILT_START_ANGLE] = angles[0]
                data[CoverEntityCapabilityAttribute.TILT_END_ANGLE] = angles[1]

        return data or None

    @final
    def _without_unsupported_speed(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Return kwargs without a speed the cover does not support."""
        speed = kwargs.get(CoverServiceArgument.SPEED)
        if speed is None or speed in (self.supported_speeds or ()):
            return kwargs
        return {k: v for k, v in kwargs.items() if k != CoverServiceArgument.SPEED}

    @final
    async def async_handle_open_cover(self, **kwargs: Any) -> None:
        """Open the cover, ignoring a speed it does not support."""
        await self.async_open_cover(**self._without_unsupported_speed(kwargs))

    @final
    async def async_handle_close_cover(self, **kwargs: Any) -> None:
        """Close the cover, ignoring a speed it does not support."""
        await self.async_close_cover(**self._without_unsupported_speed(kwargs))

    @final
    async def async_handle_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a position, ignoring a speed it does not support."""
        await self.async_set_cover_position(**self._without_unsupported_speed(kwargs))

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
        if self._is_tilt_closed():
            self.open_cover_tilt(**kwargs)
        else:
            self.close_cover_tilt(**kwargs)

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self._is_tilt_closed():
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
        # If we previously reported opening/closing, we should
        # move in the opposite direction.
        # Otherwise, we must assume we are (partially) open
        # and should always close.
        # Note: _cover_is_last_toggle_direction_open will
        # always remain True if we never report
        # opening/closing.
        return (
            fns["close"] if self._cover_is_last_toggle_direction_open else fns["open"]
        )
