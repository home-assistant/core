"""Demo platform for the cover component."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo covers."""
    async_add_entities(
        [
            DemoCover(hass, "cover_1", "Kitchen Window"),
            DemoCover(hass, "cover_2", "Hall Window", 10),
            DemoCover(hass, "cover_3", "Living Room Window", 70, 50),
            DemoCover(
                hass,
                "cover_4",
                "Garage Door",
                device_class=CoverDeviceClass.GARAGE,
                supported_features=(CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE),
            ),
            DemoCover(
                hass,
                "cover_5",
                "Pergola Roof",
                tilt_position=60,
                supported_features=(
                    CoverEntityFeature.OPEN_TILT
                    | CoverEntityFeature.STOP_TILT
                    | CoverEntityFeature.CLOSE_TILT
                    | CoverEntityFeature.SET_TILT_POSITION
                ),
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoCover(CoverEntity):
    """Representation of a demo cover."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        position: int | None = None,
        tilt_position: int | None = None,
        device_class: CoverDeviceClass | None = None,
        supported_features: int | None = None,
    ) -> None:
        """Initialize the cover."""
        self.hass = hass
        self._unique_id = unique_id
        self._attr_name = name
        self._position = position
        self._device_class = device_class
        self._supported_features = supported_features
        self._set_position: int | None = None
        self._set_tilt_position: int | None = None
        self._tilt_position = tilt_position
        self._requested_closing = True
        self._requested_closing_tilt = True
        self._unsub_listener_cover: CALLBACK_TYPE | None = None
        self._unsub_listener_cover_tilt: CALLBACK_TYPE | None = None
        self._is_opening = False
        self._is_closing = False
        if position is None:
            self._closed = True
        else:
            self._closed = position <= 0

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID for cover."""
        return self._unique_id

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self._position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        return self._tilt_position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._closed

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        if self._supported_features is not None:
            return self._supported_features
        return super().supported_features

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._position == 0:
            return
        if self._position is None:
            self._closed = True
            self.async_write_ha_state()
            return

        self._is_closing = True
        self._listen_cover()
        self._requested_closing = True
        self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if self._tilt_position in (0, None):
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = True

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._position == 100:
            return
        if self._position is None:
            self._closed = False
            self.async_write_ha_state()
            return

        self._is_opening = True
        self._listen_cover()
        self._requested_closing = False
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if self._tilt_position in (100, None):
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = False

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int = kwargs[ATTR_POSITION]
        self._set_position = round(position, -1)
        if self._position == position:
            return

        self._listen_cover()
        self._requested_closing = (
            self._position is not None and position < self._position
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover til to a specific position."""
        tilt_position: int = kwargs[ATTR_TILT_POSITION]
        self._set_tilt_position = round(tilt_position, -1)
        if self._tilt_position == tilt_position:
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = (
            self._tilt_position is not None and tilt_position < self._tilt_position
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._is_closing = False
        self._is_opening = False
        if self._position is None:
            return
        if self._unsub_listener_cover is not None:
            self._unsub_listener_cover()
            self._unsub_listener_cover = None
            self._set_position = None

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        if self._tilt_position is None:
            return

        if self._unsub_listener_cover_tilt is not None:
            self._unsub_listener_cover_tilt()
            self._unsub_listener_cover_tilt = None
            self._set_tilt_position = None

    @callback
    def _listen_cover(self) -> None:
        """Listen for changes in cover."""
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = async_track_utc_time_change(
                self.hass, self._time_changed_cover
            )

    async def _time_changed_cover(self, now: datetime) -> None:
        """Track time changes."""
        if self._position is None:
            return
        if self._requested_closing:
            self._position -= 10
        else:
            self._position += 10

        if self._position in (100, 0, self._set_position):
            await self.async_stop_cover()

        self._closed = (
            self.current_cover_position is not None and self.current_cover_position <= 0
        )
        self.async_write_ha_state()

    @callback
    def _listen_cover_tilt(self) -> None:
        """Listen for changes in cover tilt."""
        if self._unsub_listener_cover_tilt is None:
            self._unsub_listener_cover_tilt = async_track_utc_time_change(
                self.hass, self._time_changed_cover_tilt
            )

    async def _time_changed_cover_tilt(self, now: datetime) -> None:
        """Track time changes."""
        if self._tilt_position is None:
            return
        if self._requested_closing_tilt:
            self._tilt_position -= 10
        else:
            self._tilt_position += 10

        if self._tilt_position in (100, 0, self._set_tilt_position):
            await self.async_stop_cover_tilt()

        self.async_write_ha_state()
