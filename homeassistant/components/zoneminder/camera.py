"""Support for ZoneMinder camera streaming."""
import logging
from typing import Callable, Dict, List, Optional

from zoneminder.monitor import Monitor, MonitorState, TimePeriod

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
    ):
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
        self._events: Dict[str, int] = {}
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
        try:
            self._is_recording = self._monitor.is_recording
            self._is_available = self._monitor.is_available
            self._function = self._monitor.function

            for time_period in TimePeriod:
                for include_archived in (True, False):
                    archived_name = (
                        "with_archived" if include_archived else "without_archived"
                    )
                    name = f"events_{time_period.period}_{archived_name}"
                    self._events[name] = self._monitor.get_events(
                        time_period, include_archived
                    )
        except Exception:  # pylint: disable=broad-except
            self._is_available = False

    @property
    def is_recording(self):
        """Return whether the monitor is in alarm mode."""
        return self._is_recording

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def is_on(self):
        """Return true if on."""
        return self._function != MonitorState.NONE

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._function in (MonitorState.MODECT, MonitorState.MOCORD)

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        attrs = super().state_attributes
        attrs["function"] = self._function.value if self._function else None
        attrs.update(self._events)
        return attrs

    def turn_off(self):
        """Turn off camera."""
        self._monitor.function = MonitorState.NONE

    def turn_on(self):
        """Turn off camera."""
        self._monitor.function = MonitorState.MONITOR

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._monitor.function = MonitorState.MODECT

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._monitor.function = MonitorState.MONITOR
