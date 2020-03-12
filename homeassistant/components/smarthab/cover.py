"""Support for SmartHab device integration."""
from datetime import timedelta
import logging

import pysmarthab
from requests.exceptions import Timeout

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverDevice,
)

from . import DATA_HUB, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SmartHab roller shutters platform."""

    hub = hass.data[DOMAIN][DATA_HUB]
    devices = hub.get_device_list()

    _LOGGER.debug("Found a total of %s devices", str(len(devices)))

    entities = (
        SmartHabCover(cover)
        for cover in devices
        if isinstance(cover, pysmarthab.Shutter)
    )

    add_entities(entities, True)


class SmartHabCover(CoverDevice):
    """Representation a cover."""

    def __init__(self, cover):
        """Initialize a SmartHabCover."""
        self._cover = cover

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._cover.device_id

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._cover.label

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._cover.state

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

        if self.current_cover_position is not None:
            supported_features |= SUPPORT_SET_POSITION

        return supported_features

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self._cover.state == 0

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return "window"

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._cover.open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._cover.close()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self._cover.state = kwargs[ATTR_POSITION]

    def update(self):
        """Fetch new state data for this cover."""
        try:
            self._cover.update()
        except Timeout:
            _LOGGER.error(
                "Reached timeout while updating cover %s from API", self.entity_id
            )
