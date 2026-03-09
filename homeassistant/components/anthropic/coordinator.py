"""Coordinator for the Anthropic integration."""

from __future__ import annotations

from datetime import timedelta

import anthropic

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

UPDATE_INTERVAL_CONNECTED = timedelta(hours=12)
UPDATE_INTERVAL_DISCONNECTED = timedelta(minutes=1)

type AnthropicConfigEntry = ConfigEntry[AnthropicCoordinator]


class AnthropicCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator which uses different intervals after successful and unsuccessful updates."""

    client: anthropic.AsyncAnthropic

    def __init__(self, hass: HomeAssistant, config_entry: AnthropicConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL_CONNECTED,
            update_method=self.async_update_data,
            always_update=False,
        )
        self.client = anthropic.AsyncAnthropic(
            api_key=config_entry.data[CONF_API_KEY], http_client=get_async_client(hass)
        )

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule the next refresh based on the current update interval."""
        self.update_interval = (
            UPDATE_INTERVAL_CONNECTED
            if self.last_update_success
            else UPDATE_INTERVAL_DISCONNECTED
        )
        super()._schedule_refresh()

    @callback
    def async_set_updated_data(self, data: None) -> None:
        """Manually update data, notify listeners and update refresh interval."""
        self.update_interval = UPDATE_INTERVAL_CONNECTED
        super().async_set_updated_data(data)

    async def async_update_data(self) -> None:
        """Fetch data from the API."""
        try:
            await self.client.models.list(timeout=10.0)
        except anthropic.APITimeoutError as err:
            raise TimeoutError(err.message or str(err)) from err
        except anthropic.AuthenticationError as err:
            raise ConfigEntryAuthFailed(err.message or str(err)) from err
        except anthropic.APIError as err:
            raise UpdateFailed(err.message or str(err)) from err

    def mark_connection_error(self) -> None:
        """Mark the connection as having an error and reschedule background check."""
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        if self.last_update_success:
            self.last_update_success = False
            self.async_update_listeners()
            if self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()
