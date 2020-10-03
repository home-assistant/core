"""Support for ZoneMinder camera streaming."""
import logging
from typing import Any, Callable, Dict, List, Optional

from zoneminder.monitor import Monitor, MonitorState

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

from .common import get_config_data

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
    config_data = get_config_data(hass, config_entry)
    zm_client = config_data.client

    async_add_entities(
        [
            ZoneMinderCamera(hass, monitor, zm_client.verify_ssl, config_entry)
            for monitor in await hass.async_add_executor_job(zm_client.get_monitors)
        ]
    )


class ZoneMinderCamera(MjpegCamera):
    """Representation of a ZoneMinder Monitor Stream."""

    def __init__(
        self,
        hass: HomeAssistant,
        monitor: Monitor,
        verify_ssl: bool,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize as a subclass of MjpegCamera."""
        device_info = {
            CONF_NAME: monitor.name,
            CONF_MJPEG_URL: monitor.mjpeg_image_url,
            CONF_STILL_IMAGE_URL: monitor.still_image_url,
            CONF_VERIFY_SSL: verify_ssl,
        }
        super().__init__(device_info)
        self._hass = hass
        self._is_recording = None
        self._is_available = None
        self._function: Optional[MonitorState] = None
        self._monitor = monitor
        self._config_entry = config_entry

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_camera"

    @property
    def should_poll(self) -> bool:
        """Update the recording state periodically."""
        return True

    def update(self) -> None:
        """Update our recording state from the ZM API."""
        _LOGGER.debug("Updating camera state for monitor %i", self._monitor.id)
        try:
            self._is_recording = self._monitor.is_recording
            self._is_available = self._monitor.is_available
            self._function = self._monitor.function
        except Exception:  # pylint: disable=broad-except
            self._is_available = False

    @property
    def is_recording(self) -> bool:
        """Return whether the monitor is in alarm mode."""
        return self._is_recording

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self._function != MonitorState.NONE

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._function in (MonitorState.MODECT, MonitorState.MOCORD)

    @property
    def state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the camera state attributes."""
        attrs = super().state_attributes
        attrs["monitor_id"] = self._monitor.id
        attrs["function"] = self._function.value if self._function else None
        return attrs

    def turn_off(self) -> None:
        """Turn off camera."""
        self._monitor.function = MonitorState.NONE
        self.is_streaming = False

    def turn_on(self) -> None:
        """Turn off camera."""
        self._monitor.function = MonitorState.MONITOR
        self.is_streaming = True

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        self._monitor.function = MonitorState.MODECT
        self.is_streaming = True

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        if self._function == MonitorState.MODECT:
            self._monitor.function = MonitorState.MONITOR
