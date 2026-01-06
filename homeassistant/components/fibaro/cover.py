"""Support for Fibaro cover - curtains, rollershutters etc."""

from __future__ import annotations

from typing import Any, cast

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    ENTITY_ID_FORMAT,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FibaroConfigEntry
from .entity import FibaroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FibaroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fibaro covers."""
    controller = entry.runtime_data

    entities: list[FibaroEntity] = []
    for device in controller.fibaro_devices[Platform.COVER]:
        # Positionable covers report the position over value
        if device.value.has_value:
            entities.append(PositionableFibaroCover(device))
        else:
            entities.append(FibaroCover(device))
    async_add_entities(entities, True)


class PositionableFibaroCover(FibaroEntity, CoverEntity):
    """Representation of a fibaro cover which supports positioning."""

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    @staticmethod
    def bound(position: int | None) -> int | None:
        """Normalize the position."""
        if position is None:
            return None
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def update(self) -> None:
        """Update the state."""
        super().update()

        self._attr_current_cover_position = self.bound(self.level)
        self._attr_current_cover_tilt_position = self.bound(self.level2)

        # Be aware that opening and closing is only available for some modern
        # devices.
        # For example the Fibaro Roller Shutter 4 reports this correctly.
        device_state = self.fibaro_device.state.str_value(default="").lower()
        self._attr_is_opening = device_state == "opening"
        self._attr_is_closing = device_state == "closing"

        closed: bool | None = None
        if self.current_cover_position is not None:
            closed = self.current_cover_position == 0
        self._attr_is_closed = closed

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.set_level(cast(int, kwargs.get(ATTR_POSITION)))

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the slats to a specific position."""
        self.set_level2(cast(int, kwargs.get(ATTR_TILT_POSITION)))

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.action("open")

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.action("close")

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        self.set_level2(100)

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.set_level2(0)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self.action("stop")


class FibaroCover(FibaroEntity, CoverEntity):
    """Representation of a fibaro cover which supports only open / close commands."""

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if "stop" in self.fibaro_device.actions:
            self._attr_supported_features |= CoverEntityFeature.STOP
        if "rotateSlatsUp" in self.fibaro_device.actions:
            self._attr_supported_features |= CoverEntityFeature.OPEN_TILT
        if "rotateSlatsDown" in self.fibaro_device.actions:
            self._attr_supported_features |= CoverEntityFeature.CLOSE_TILT
        if "stopSlats" in self.fibaro_device.actions:
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT

    def update(self) -> None:
        """Update the state."""
        super().update()

        device_state = self.fibaro_device.state.str_value(default="").lower()

        self._attr_is_opening = device_state == "opening"
        self._attr_is_closing = device_state == "closing"

        closed: bool | None = None
        if device_state not in {"", "unknown"}:
            closed = device_state == "closed"
        self._attr_is_closed = closed

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.action("open")

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.action("close")

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self.action("stop")

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover slats."""
        self.action("rotateSlatsUp")

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover slats."""
        self.action("rotateSlatsDown")

    def stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover slats turning."""
        self.action("stopSlats")
