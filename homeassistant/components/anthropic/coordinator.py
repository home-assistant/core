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
        super().async_set_updated_data(None)

    @callback
    def async_set_update_error(self, err: Exception) -> None:
        """Manually set an error and reschedule next update."""
        err = self._map_exception(err)
        super().async_set_update_error(err)
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED

        if isinstance(err, UpdateFailed) and err.retry_after is not None:
            self._retry_after = err.retry_after
            self.logger.debug(
                "Retry after triggered. Scheduling next update in %s second(s)",
                err.retry_after,
            )

        if isinstance(err, ConfigEntryAuthFailed):
            self.logger.debug("Authentication failed, reauthentication required")
            self._async_unsub_refresh()
            self._debounced_refresh.async_cancel()
            if self.config_entry is not None:
                self.config_entry.async_start_reauth(self.hass)
        elif self._listeners and not self.hass.is_stopping:
            self._schedule_refresh()

    def _map_exception(self, err: Exception) -> Exception:
        """Map Anthropic API exceptions to Home Assistant exceptions."""
        message = getattr(err, "message", None) or str(err)
        exc = err
        if isinstance(err, anthropic.APITimeoutError):
            exc = TimeoutError(message)
        elif isinstance(err, anthropic.AuthenticationError):
            exc = ConfigEntryAuthFailed(message)
        elif isinstance(err, anthropic.APIError):
            exc = UpdateFailed(message)
        if exc is not err:
            exc.__cause__ = err
            exc.__suppress_context__ = True
        return exc

    async def async_update_data(self) -> None:
        """Fetch data from the API."""
        try:
            await self.client.models.list(timeout=10.0)
        except anthropic.AnthropicError as err:
            raise self._map_exception(err)  # noqa: B904
