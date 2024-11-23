"""Support for OpenUV sunscreen reminder."""

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import SUNSCREEN_DOMAIN

# Constants
LOCAL_TIMEZONE = "Europe/Stockholm"
UV_SENSOR = "sensor.openuv_current_uv_index"
UV_THRESHOLD = 3  # In real life should be 3 (For demo lower values)
NOTIFICATION_INTERVAL_HOURS = 0.0166  # Equal to 1 min (For demo lower values)
CHECK_INTERVAL_MINUTES = 0.5  # Frequency to check the UV index

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
        if self.periodic_task:
            _LOGGER.debug("Periodic task already running, skipping initialization")
            return

        _LOGGER.debug("Initializing SunscreenReminder")
        self.periodic_task = async_track_time_interval(
            self.hass, self._periodic_check, timedelta(minutes=CHECK_INTERVAL_MINUTES)
        )

    async def _periodic_check(self, now):
        """Periodic check triggered by time interval."""
        _LOGGER.debug("Periodic check triggered at %s", now)

        # Check the state of the switch entity
        switch_state = self.hass.states.get("switch.sunscreen_reminder")
        if not switch_state or switch_state.state != "on":
            _LOGGER.debug("Sunscreen reminder is disabled, skipping check")
            return

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
            if (
                self.last_notification_time is None
                or now - self.last_notification_time
                >= timedelta(hours=NOTIFICATION_INTERVAL_HOURS)
            ):
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
            _LOGGER.debug("Periodic task stopped")


async def async_setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the Sunscreen Reminder integration."""
    _LOGGER.debug("Setting up Sunscreen Reminder")

    # Ensure the reminder instance is created and initialized
    if SUNSCREEN_DOMAIN not in hass.data:
        hass.data[SUNSCREEN_DOMAIN] = SunscreenReminder(hass)
    else:
        _LOGGER.warning("SunscreenReminder already exists in hass.data")

    # Initialize the reminder (start periodic tasks)
    await hass.data[SUNSCREEN_DOMAIN].async_initialize()

    # Load the switch platform
    hass.helpers.discovery.async_load_platform("switch", SUNSCREEN_DOMAIN, {}, config)

    return True
