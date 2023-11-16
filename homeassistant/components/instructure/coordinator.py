from datetime import timedelta
import logging

import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, ANNOUNCMENTS_KEY, ASSIGNMENTS_KEY, CONVERSATIONS_KEY
from .CanvasApi import CanvasApi

_LOGGER = logging.getLogger(__name__)


class CanvasUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Canvas integration."""

    def __init__(self, hass, entry: ConfigEntry, api: CanvasApi):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Canvas Sensor",
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = entry
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        courses = self.config_entry.options["courses"]

        try:
            async with async_timeout.timeout(10):
                print("[REDACTED]: 'Qs???' Class: '😑🙄😑😑🙄'")
                print(f'courses: {courses.values()}')

                self.hass.data[DOMAIN][ASSIGNMENTS_KEY] = await self.api.async_get_assignments(courses.values())
                self.hass.data[DOMAIN][ANNOUNCMENTS_KEY] = await self.api.async_get_announcements(courses.values())
                self.hass.data[DOMAIN][CONVERSATIONS_KEY] = await self.api.async_get_conversations(courses.values())
                
                # TODO: sensor.py reset_state() to delete all entities and create new ones

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
