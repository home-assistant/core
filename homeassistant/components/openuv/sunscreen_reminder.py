"""Support for OpenUV sunscreen reminder."""

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

# Constants
LOCAL_TIMEZONE = "Europe/Stockholm"
UV_SENSOR = "sensor.openuv_current_uv_index"
UV_THRESHOLD = 3  # In real life should be 3 (For demo lower values)
NOTIFICATION_INTERVAL_HOURS = 0.0833  # Equal to 5min (In real life set it to 2(hours))
CHECK_INTERVAL_MINUTES = 1  # Frequency to check the UV index

_LOGGER = logging.getLogger(__name__)


class SunscreenReminder:
    """Class to manage sunscreen reminders."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the SunscreenReminder class."""
        self.hass = hass
        self.last_notification_time = None
        self.periodic_task = None

    async def async_initialize(self):
        """Asynchronously initialize the Sunscreen Reminder."""
        _LOGGER.debug("Initializing SunscreenReminder")

        # Set up periodic UV index checks
        self.periodic_task = async_track_time_interval(
            self.hass, self._periodic_check, timedelta(minutes=CHECK_INTERVAL_MINUTES)
        )

    async def _periodic_check(self, now):
        _LOGGER.debug("Periodic check triggered at %s", now)

        state = self.hass.states.get(UV_SENSOR)
        if not state:
            _LOGGER.error("Sensor %s not found in state machine", UV_SENSOR)
            return

        if state.state in (None, "unknown"):
            _LOGGER.warning("Sensor %s has no valid state: %s", UV_SENSOR, state.state)
            return

        try:
            uv_index = float(state.state)
            _LOGGER.debug("Current UV index: %s", uv_index)
            self._handle_uv_index(uv_index)
        except ValueError:
            _LOGGER.warning("Invalid UV index value for %s: %s", UV_SENSOR, state.state)

    def _handle_uv_index(self, uv_index):
        now = datetime.now()
        _LOGGER.debug("Handling UV index: %s", uv_index)
        if uv_index >= UV_THRESHOLD:
            _LOGGER.debug(
                "UV index %s meets or exceeds threshold %s", uv_index, UV_THRESHOLD
            )
            if (
                self.last_notification_time is None
                or now - self.last_notification_time
                >= timedelta(hours=NOTIFICATION_INTERVAL_HOURS)
            ):
                _LOGGER.debug("Time since last notification allows sending a new one")
                self.last_notification_time = now
                self.hass.async_create_task(self._send_notification())
            else:
                _LOGGER.debug("Notification interval not met")
        else:
            _LOGGER.debug(
                "UV index %s below threshold %s. No notification sent",
                uv_index,
                UV_THRESHOLD,
            )

    async def _send_notification(self):
        """Asynchronously send a sunscreen reminder notification."""
        now = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S %Z")
        message = f"Save your skin, apply sunscreen!\n\n{now}"
        await self.hass.services.async_call(
            domain="persistent_notification",
            service="create",
            service_data={"message": message, "title": "Sunscreen Reminder"},
        )

        _LOGGER.info("Sunscreen reminder notification sent")

    async def async_cleanup(self):
        """Clean up resources."""
        if self.periodic_task:
            self.periodic_task()
            self.periodic_task = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sunscreen Reminder integration."""
    _LOGGER.debug("Setting up Sunscreen Reminder")
    reminder = SunscreenReminder(hass)
    await reminder.async_initialize()
    hass.data.setdefault("sunscreen_reminder", reminder)
    return True
