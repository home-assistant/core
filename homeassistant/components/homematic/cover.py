"""Support for  HomeMatic covers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DEVICE_TYPE, ATTR_DISCOVER_DEVICES
from .entity import HMDevice

HM_GARAGE = ("IPGarage",)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform."""
    if discovery_info is None:
        return

    devices: list[HMCover] = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        if conf[ATTR_DEVICE_TYPE] in HM_GARAGE:
            devices.append(HMGarage(conf))
        else:
            devices.append(HMCover(conf))

    add_entities(devices, True)


class HMCover(HMDevice, CoverEntity):
    """Representation a HomeMatic Cover."""

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return int(self._hm_get_state() * 100)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = float(kwargs[ATTR_POSITION])
            position = min(100, max(0, position))
            level = position / 100.0
            self._hmdevice.set_level(level, self._channel)

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0
        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._hmdevice.move_up(self._channel)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._hmdevice.move_down(self._channel)

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        self._hmdevice.stop(self._channel)

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        self._state = "LEVEL"
        self._data.update({self._state: None})
        if "LEVEL_2" in self._hmdevice.WRITENODE:
            self._data.update({"LEVEL_2": None})

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if not (position := self._data.get("LEVEL_2", 0)):
            return None
        return int(position * 100)

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if "LEVEL_2" in self._data and ATTR_TILT_POSITION in kwargs:
            position = float(kwargs[ATTR_TILT_POSITION])
            position = min(100, max(0, position))
            level = position / 100.0
            self._hmdevice.set_cover_tilt_position(level, self._channel)

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if "LEVEL_2" in self._data:
            self._hmdevice.open_slats()

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if "LEVEL_2" in self._data:
            self._hmdevice.close_slats()

    def stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        if "LEVEL_2" in self._data:
            self.stop_cover(**kwargs)


class HMGarage(HMCover):
    """Represents a Homematic Garage cover. Homematic garage covers do not support position attributes."""

    _attr_device_class = CoverDeviceClass.GARAGE

    @property
    def current_cover_position(self) -> None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # Garage covers do not support position; always return None
        return None

    @property
    def is_closed(self) -> bool:
        """Return whether the cover is closed."""
        return self._hmdevice.is_closed(self._hm_get_state())

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        self._state = "DOOR_STATE"
        self._data.update({self._state: None})
