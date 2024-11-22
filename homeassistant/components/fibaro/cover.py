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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FibaroController
from .const import DOMAIN
from .entity import FibaroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro covers."""
    controller: FibaroController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [FibaroCover(device) for device in controller.fibaro_devices[Platform.COVER]],
        True,
    )


class FibaroCover(FibaroEntity, CoverEntity):
    """Representation a Fibaro Cover."""

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the Vera device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        if self._is_open_close_only():
            self._attr_supported_features = (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            )
            if "stop" in self.fibaro_device.actions:
                self._attr_supported_features |= CoverEntityFeature.STOP

    @staticmethod
    def bound(position):
        """Normalize the position."""
        if position is None:
            return None
        position = int(position)
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def _is_open_close_only(self) -> bool:
        """Return if only open / close is supported."""
        # Normally positionable devices report the position over value,
        # so if it is missing we have a device which supports open / close only
        return not self.fibaro_device.value.has_value

    def update(self) -> None:
        """Update the state."""
        super().update()

        self._attr_current_cover_position = self.bound(self.level)
        self._attr_current_cover_tilt_position = self.bound(self.level2)

        device_state = self.fibaro_device.state

        # Be aware that opening and closing is only available for some modern
        # devices.
        # For example the Fibaro Roller Shutter 4 reports this correctly.
        if device_state.has_value:
            self._attr_is_opening = device_state.str_value().lower() == "opening"
            self._attr_is_closing = device_state.str_value().lower() == "closing"

        closed: bool | None = None
        if self._is_open_close_only():
            if device_state.has_value and device_state.str_value().lower() != "unknown":
                closed = device_state.str_value().lower() == "closed"
        elif self.current_cover_position is not None:
            closed = self.current_cover_position == 0
        self._attr_is_closed = closed

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.set_level(cast(int, kwargs.get(ATTR_POSITION)))

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
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
