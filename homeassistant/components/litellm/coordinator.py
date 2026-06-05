"""Coordinator for the LiteLLM integration."""

from datetime import timedelta
from typing import Any, cast

from litellm.proxy.client import Client
from litellm.proxy.client.exceptions import UnauthorizedError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

# Ping the proxy hourly while it is reachable, and back off to once a minute
# while it is down so entities recover quickly once it returns.
UPDATE_INTERVAL_CONNECTED = timedelta(hours=1)
UPDATE_INTERVAL_DISCONNECTED = timedelta(minutes=1)

type LiteLLMConfigEntry = ConfigEntry[LiteLLMDataUpdateCoordinator]


def list_proxy_models(url: str, api_key: str | None) -> list[str]:
    """Return the model names served by the proxy.

    Uses the LiteLLM proxy client, which is synchronous, so callers must run
    this in the executor.
    """
    client = Client(base_url=url, api_key=api_key)
    models = cast(list[dict[str, Any]], client.models.list())
    return [model["id"] for model in models]


class LiteLLMDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Track LiteLLM proxy availability via periodic model-list pings."""

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
        self.url: str = config_entry.data[CONF_URL]
        self.api_key: str | None = config_entry.data.get(CONF_API_KEY)

    async def _async_update_data(self) -> None:
        """Ping the proxy to confirm it is reachable and authenticated."""
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        try:
            await self.hass.async_add_executor_job(
                list_proxy_models, self.url, self.api_key
            )
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except requests.RequestException as err:
            raise UpdateFailed(err) from err
        self.update_interval = UPDATE_INTERVAL_CONNECTED

    @callback
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
