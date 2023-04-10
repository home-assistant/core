"""Support for Fibaro cover - curtains, rollershutters etc."""
from __future__ import annotations

from typing import Any

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

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro covers."""
    async_add_entities(
        [
            FibaroCover(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.COVER
            ]
        ],
        True,
    )


class FibaroCover(FibaroDevice, CoverEntity):
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

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover. 0 is closed, 100 is open."""
        return self.bound(self.level)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position for venetian blinds."""
        return self.bound(self.level2)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.set_level(kwargs.get(ATTR_POSITION))

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.set_level2(kwargs.get(ATTR_TILT_POSITION))

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._is_open_close_only():
            state = self.fibaro_device.state
            if not state.has_value or state.str_value().lower() == "unknown":
                return None
            return state.str_value().lower() == "closed"

        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

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
