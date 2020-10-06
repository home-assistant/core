"""Support for ZoneMinder camera streaming."""
import logging
from typing import Callable, List, Optional

from zoneminder.monitor import Monitor

from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    MjpegCamera,
    filter_urllib3_logging,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import get_client_from_data

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder cameras."""
    filter_urllib3_logging()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    zm_client = get_client_from_data(hass, config_entry.unique_id)

    async_add_entities(
        [
            ZoneMinderCamera(monitor, zm_client.verify_ssl, config_entry)
            for monitor in await hass.async_add_job(zm_client.get_monitors)
        ]
    )


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    def __init__(self, monitor: Monitor, verify_ssl: bool, config_entry: ConfigEntry):
        """Initialize as a subclass of MjpegCamera."""
        device_info = {
            CONF_NAME: monitor.name,
            CONF_MJPEG_URL: monitor.mjpeg_image_url,
            CONF_STILL_IMAGE_URL: monitor.still_image_url,
            CONF_VERIFY_SSL: verify_ssl,
        }
        super().__init__(device_info)
        self._is_recording = None
        self._is_available = None
        self._monitor = monitor
        self._config_entry = config_entry

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_camera"

    @property
    def should_poll(self):
        """Update the recording state periodically."""
        return True

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
