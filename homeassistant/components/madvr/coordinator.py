"""Coordinator for handling data fetching and updates."""

import logging

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MadVRCoordinator(DataUpdateCoordinator):
    """My custom coordinator for push-based API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        my_api: Madvr,
        mac: str,
        name: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="My API Coordinator",
        )
        self.entry_id = config_entry.entry_id
        self.my_api = my_api
        self.mac = mac
        self.name = name
        self.previous_data: dict = {}
        self.my_api.set_update_callback(self.handle_push_data)
        _LOGGER.debug("MadVRCoordinator initialized")

    async def _async_update_data(self):
        """No-op method for initial setup."""
        return self.previous_data

    def handle_push_data(self, data: dict):
        """Handle new data pushed from the API."""
        _LOGGER.debug("Received push data: %s", data)
        if self.previous_data:
            # Compare power state
            if data.get("is_on") != self.previous_data.get("is_on"):
                event_data = {
                    "device_id": self.entry_id,
                    "type": "power_state_changed",
                    "new_state": data.get("is_on"),
                    "old_state": self.previous_data.get("is_on"),
                }
                self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

            # Compare HDR flag
            if data.get("hdr_flag") != self.previous_data.get("hdr_flag"):
                event_data = {
                    "device_id": self.entry_id,
                    "type": "hdr_flag_changed",
                    "new_state": data.get("hdr_flag"),
                    "old_state": self.previous_data.get("hdr_flag"),
                }
                self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

            # Compare aspect ratio
            if data.get("aspect_dec") != self.previous_data.get("aspect_dec"):
                event_data = {
                    "device_id": self.entry_id,
                    "type": "aspect_dec_changed",
                    "new_state": data.get("aspect_dec"),
                    "old_state": self.previous_data.get("aspect_dec"),
                }
                self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

        self.previous_data = data
        self.async_set_updated_data(data)
