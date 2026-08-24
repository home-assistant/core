"""Coordinator for the LiteLLM integration."""

from datetime import timedelta
from typing import override

from openai import AsyncOpenAI, AuthenticationError, OpenAIError, PermissionDeniedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, PLACEHOLDER_API_KEY

# Ping the proxy hourly while it is reachable, and back off to once a minute
# while it is down so entities recover quickly once it returns.
UPDATE_INTERVAL_CONNECTED = timedelta(hours=1)
UPDATE_INTERVAL_DISCONNECTED = timedelta(minutes=1)

type LiteLLMConfigEntry = ConfigEntry[LiteLLMDataUpdateCoordinator]


class LiteLLMDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Own the OpenAI client and track LiteLLM proxy availability."""

    config_entry: LiteLLMConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: LiteLLMConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL_CONNECTED,
            always_update=False,
        )
        self.client = AsyncOpenAI(
            base_url=config_entry.data[CONF_URL],
            api_key=config_entry.data.get(CONF_API_KEY) or PLACEHOLDER_API_KEY,
            http_client=get_async_client(hass),
        )

    @override
    async def _async_update_data(self) -> None:
        """Ping the proxy to confirm it is reachable and authenticated."""
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        try:
            async for _ in self.client.with_options(timeout=10.0).models.list():
                break
        except (AuthenticationError, PermissionDeniedError) as err:
            raise ConfigEntryAuthFailed from err
        except OpenAIError as err:
            raise UpdateFailed(err) from err
        self.update_interval = UPDATE_INTERVAL_CONNECTED

    @callback
    @override
    def async_set_updated_data(self, data: None) -> None:
        """Manually update data and reset to the connected interval."""
        self.update_interval = UPDATE_INTERVAL_CONNECTED
        super().async_set_updated_data(data)

    @callback
    def mark_connection_error(self) -> None:
        """Flag the proxy as unreachable and schedule a quick recheck."""
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        if self.last_update_success:
            self.last_update_success = False
            self.async_update_listeners()
            if self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()
