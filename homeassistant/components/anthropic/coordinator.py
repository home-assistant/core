"""Coordinator for the Anthropic integration."""

from __future__ import annotations

import datetime
import re

import anthropic

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

UPDATE_INTERVAL_CONNECTED = datetime.timedelta(hours=12)
UPDATE_INTERVAL_DISCONNECTED = datetime.timedelta(minutes=1)

type AnthropicConfigEntry = ConfigEntry[AnthropicCoordinator]


_model_short_form = re.compile(r"[^\d]-\d$")


@callback
def model_alias(model_id: str) -> str:
    """Resolve alias from versioned model name."""
    if model_id == "claude-3-haiku-20240307" or model_id.endswith("-preview"):
        return model_id
    if model_id[-2:-1] != "-":
        model_id = model_id[:-9]
    if _model_short_form.search(model_id):
        return model_id + "-0"
    return model_id


class AnthropicCoordinator(DataUpdateCoordinator[list[anthropic.types.ModelInfo]]):
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
    def async_set_updated_data(self, data: list[anthropic.types.ModelInfo]) -> None:
        """Manually update data, notify listeners and update refresh interval."""
        self.update_interval = UPDATE_INTERVAL_CONNECTED
        super().async_set_updated_data(data)

    async def async_update_data(self) -> list[anthropic.types.ModelInfo]:
        """Fetch data from the API."""
        try:
            self.update_interval = UPDATE_INTERVAL_DISCONNECTED
            result = await self.client.models.list(timeout=10.0)
            self.update_interval = UPDATE_INTERVAL_CONNECTED
        except anthropic.APITimeoutError as err:
            raise TimeoutError(err.message or str(err)) from err
        except anthropic.AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="api_authentication_error",
                translation_placeholders={"message": err.message},
            ) from err
        except anthropic.APIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"message": err.message},
            ) from err
        return result.data

    def mark_connection_error(self) -> None:
        """Mark the connection as having an error and reschedule background check."""
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        if self.last_update_success:
            self.last_update_success = False
            self.async_update_listeners()
            if self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()

    @callback
    def get_model_info(self, model_id: str) -> tuple[anthropic.types.ModelInfo, bool]:
        """Get model info for a given model ID."""
        # First try: exact name match
        for model in self.data or []:
            if model.id == model_id:
                return model, True
        # Second try: match by alias
        alias = model_alias(model_id)
        for model in self.data or []:
            if model_alias(model.id) == alias:
                return model, True
        # Model not found, return safe defaults
        return anthropic.types.ModelInfo(
            type="model",
            id=model_id,
            created_at=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC),
            display_name=alias,
        ), False
