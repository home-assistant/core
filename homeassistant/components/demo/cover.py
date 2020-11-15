"""Demo platform for the cover component."""
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_utc_time_change

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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
                device_class="garage",
                supported_features=(SUPPORT_OPEN | SUPPORT_CLOSE),
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoCover(CoverEntity):
    """Representation of a demo cover."""

    def __init__(
        self,
        hass,
        unique_id,
        name,
        position=None,
        tilt_position=None,
        device_class=None,
        supported_features=None,
    ):
        """Initialize the cover."""
        self.hass = hass
        self._unique_id = unique_id
        self._name = name
        self._position = position
        self._device_class = device_class
        self._supported_features = supported_features
        self._set_position = None
        self._set_tilt_position = None
        self._tilt_position = tilt_position
        self._requested_closing = True
        self._requested_closing_tilt = True
        self._unsub_listener_cover = None
        self._unsub_listener_cover_tilt = None
        self._is_opening = False
        self._is_closing = False
        if position is None:
            self._closed = True
        else:
            self._closed = self.current_cover_position <= 0

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
        }

    @property
    def unique_id(self):
        """Return unique ID for cover."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return False

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._position

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position of the cover."""
        return self._tilt_position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._supported_features is not None:
            return self._supported_features
        return super().supported_features

    async def async_close_cover(self, **kwargs):
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

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        if self._tilt_position in (0, None):
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = True

    async def async_open_cover(self, **kwargs):
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

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        if self._tilt_position in (100, None):
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = False

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        self._set_position = round(position, -1)
        if self._position == position:
            return

        self._listen_cover()
        self._requested_closing = position < self._position

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover til to a specific position."""
        tilt_position = kwargs.get(ATTR_TILT_POSITION)
        self._set_tilt_position = round(tilt_position, -1)
        if self._tilt_position == tilt_position:
            return

        self._listen_cover_tilt()
        self._requested_closing_tilt = tilt_position < self._tilt_position

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._is_closing = False
        self._is_opening = False
        if self._position is None:
            return
        if self._unsub_listener_cover is not None:
            self._unsub_listener_cover()
            self._unsub_listener_cover = None
            self._set_position = None

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        if self._tilt_position is None:
            return

        if self._unsub_listener_cover_tilt is not None:
            self._unsub_listener_cover_tilt()
            self._unsub_listener_cover_tilt = None
            self._set_tilt_position = None

    @callback
    def _listen_cover(self):
        """Listen for changes in cover."""
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = async_track_utc_time_change(
                self.hass, self._time_changed_cover
            )

    async def _time_changed_cover(self, now):
        """Track time changes."""
        if self._requested_closing:
            self._position -= 10
        else:
            self._position += 10

        if self._position in (100, 0, self._set_position):
            await self.async_stop_cover()

        self._closed = self.current_cover_position <= 0
        self.async_write_ha_state()

    @callback
    def _listen_cover_tilt(self):
        """Listen for changes in cover tilt."""
        if self._unsub_listener_cover_tilt is None:
            self._unsub_listener_cover_tilt = async_track_utc_time_change(
                self.hass, self._time_changed_cover_tilt
            )

    async def _time_changed_cover_tilt(self, now):
        """Track time changes."""
        if self._requested_closing_tilt:
            self._tilt_position -= 10
        else:
            self._tilt_position += 10

        if self._tilt_position in (100, 0, self._set_tilt_position):
            await self.async_stop_cover_tilt()

        self.async_write_ha_state()
