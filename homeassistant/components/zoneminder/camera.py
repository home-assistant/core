"""Support for ZoneMinder camera streaming."""

import logging

from zoneminder.monitor import Monitor

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZoneMinderConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZoneMinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZoneMinder cameras."""
    filter_urllib3_logging()
    verify_ssl = entry.runtime_data.client.verify_ssl
    async_add_entities(
        ZoneMinderCamera(monitor, entry.entry_id, verify_ssl)
        for monitor in entry.runtime_data.monitors
    )


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    _attr_should_poll = True  # Cameras default to False

    def __init__(self, monitor: Monitor, entry_id: str, verify_ssl: bool) -> None:
        """Initialize as a subclass of MjpegCamera."""
        super().__init__(
            name=monitor.name,
            mjpeg_url=monitor.mjpeg_image_url,
            still_image_url=monitor.still_image_url,
            verify_ssl=verify_ssl,
            unique_id=f"{entry_id}_{monitor.id}",
        )
        self._attr_is_recording = False
        self._attr_available = False
        self._monitor = monitor

    def update(self) -> None:
        """Update our recording state from the ZM API."""
        _LOGGER.debug("Updating camera state for monitor %i", self._monitor.id)
        self._attr_is_recording = self._monitor.is_recording
        self._attr_available = self._monitor.is_available
