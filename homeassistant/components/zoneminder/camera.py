"""Support for ZoneMinder camera streaming."""
from __future__ import annotations

import logging

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as ZONEMINDER_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder cameras."""
    filter_urllib3_logging()
    cameras = []
    for zm_client in hass.data[ZONEMINDER_DOMAIN].values():
        if not (monitors := zm_client.get_monitors()):
            _LOGGER.warning("Could not fetch monitors from ZoneMinder host: %s")
            return

        for monitor in monitors:
            _LOGGER.info("Initializing camera %s", monitor.id)
            cameras.append(ZoneMinderCamera(monitor, zm_client.verify_ssl))
    add_entities(cameras)


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    _attr_should_poll = True  # Cameras default to False

    def __init__(self, monitor, verify_ssl):
        """Initialize as a subclass of MjpegCamera."""
        super().__init__(
            name=monitor.name,
            mjpeg_url=monitor.mjpeg_image_url,
            still_image_url=monitor.still_image_url,
            verify_ssl=verify_ssl,
        )
        self._is_recording = None
        self._is_available = None
        self._monitor = monitor

    def update(self):
        """Update our recording state from the ZM API."""
        _LOGGER.debug("Updating camera state for monitor %i", self._monitor.id)
        self._is_recording = self._monitor.is_recording
        self._is_available = self._monitor.is_available

    @property
    def is_recording(self):
        """Return whether the monitor is in alarm mode."""
        return self._is_recording

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available
