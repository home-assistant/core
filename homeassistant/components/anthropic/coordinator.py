"""Coordinator for the Anthropic integration."""

import datetime as dt
from functools import partial
import re
from typing import Literal, override

import anthropic
from anthropic.resources.messages.messages import DEPRECATED_MODELS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER

UPDATE_INTERVAL_CONNECTED = dt.timedelta(hours=12)
UPDATE_INTERVAL_DISCONNECTED = dt.timedelta(minutes=1)
SDK_DATE_PATTERN = re.compile(
    r"([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?, (\d{4})"  # codespell:ignore nd
)
SDK_DATE_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

type AnthropicConfigEntry = ConfigEntry[AnthropicCoordinator]


async def async_create_client(
    hass: HomeAssistant, api_key: str
) -> anthropic.AsyncAnthropic:
    """Create an Anthropic client."""
    return await hass.async_add_executor_job(
        partial(
            anthropic.AsyncAnthropic,
            api_key=api_key,
            http_client=get_async_client(hass),
        )
    )


@callback
def model_alias(model_id: str) -> str:
    """Resolve alias from versioned model name."""
    model, _, version = model_id.rpartition("-")
    if len(version) == 8 and version.isdecimal():
        return model
    return model_id


def _parse_sdk_retirement_date(value: str) -> dt.datetime | None:
    """Parse SDK retirement dates without relying on the process locale."""
    try:
        retires_at = dt_util.parse_datetime(value)
    except ValueError:
        retires_at = None
    if retires_at is not None:
        if retires_at.tzinfo is None:
            return retires_at.replace(tzinfo=dt.UTC)
        return retires_at.astimezone(dt.UTC)
    if not (match := SDK_DATE_PATTERN.fullmatch(value)):
        return None
    try:
        month = SDK_DATE_MONTHS.index(match[1].lower()) + 1
        return dt.datetime(int(match[3]), month, int(match[2]), tzinfo=dt.UTC)
    except ValueError:
        return None


class AnthropicCoordinator(DataUpdateCoordinator[list[anthropic.types.ModelInfo]]):
    """Coordinator using different intervals after success and failure."""

    config_entry: AnthropicConfigEntry
    _client: anthropic.AsyncAnthropic

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
        self._last_model_update: dt.datetime | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Return the Anthropic client."""
        return self._client

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self._client = await async_create_client(
            self.hass, self.config_entry.data[CONF_API_KEY]
        )

    async def async_update_data(self) -> list[anthropic.types.ModelInfo]:
        """Fetch model list from the API.

        Regular updates fetch active models.
        Deprecated and retired models are only fetched on first refresh,
        if the active models have changed, if a deprecation date has passed
        since the previous update, or if a deprecated model's retirement date is past.
        """
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        active_models = await self._async_get_models(["active"])
        models = self.data or []
        cached_active_models = [
            model for model in models if model.lifecycle == "active"
        ]
        last_update = self._last_model_update
        now = dt_util.utcnow()
        if (
            last_update is None
            or active_models != cached_active_models
            or any(
                model.retires_at is not None and model.retires_at <= now
                for model in models
                if model.lifecycle == "deprecated"
            )
            or any(
                last_update < model.deprecated_at <= now
                for model in models
                if model.deprecated_at is not None
            )
        ):
            inactive_models = await self._async_get_models(["deprecated", "retired"])
        else:
            inactive_models = [model for model in models if model.lifecycle != "active"]
        # A model can change lifecycle between the two requests.
        inactive_ids = {model.id for model in inactive_models}
        models = [
            model for model in active_models if model.id not in inactive_ids
        ] + inactive_models
        self._last_model_update = now
        self.update_interval = UPDATE_INTERVAL_CONNECTED
        return models

    async def _async_get_models(
        self, lifecycle: list[Literal["active", "deprecated", "retired"]]
    ) -> list[anthropic.types.ModelInfo]:
        """Fetch all pages for the requested lifecycle stages."""
        try:
            result = await self.client.models.list(lifecycle=lifecycle, timeout=10.0)
            return [model async for model in result]
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

    @callback
    def mark_connection_healthy(self) -> None:
        """Restore connection health without changing catalogue polling."""
        if not self.last_update_success:
            self.last_update_success = True
            self.async_update_listeners()

    def mark_connection_error(self) -> None:
        """Mark the connection as having an error and reschedule background check."""
        reschedule_refresh = self.update_interval != UPDATE_INTERVAL_DISCONNECTED
        self.update_interval = UPDATE_INTERVAL_DISCONNECTED
        if self.last_update_success:
            self.last_update_success = False
            self.async_update_listeners()
        if reschedule_refresh and self._listeners and not self.hass.is_stopping:
            self._schedule_refresh()

    @callback
    def get_model_info(self, model_id: str) -> tuple[anthropic.types.ModelInfo, bool]:
        """Get model info for a given model ID."""
        alias = model_alias(model_id)
        model = next((model for model in self.data or [] if model.id == model_id), None)
        if model is None:
            model = next(
                (model for model in self.data or [] if model_alias(model.id) == alias),
                None,
            )
        if model is None:
            return anthropic.types.ModelInfo(
                type="model",
                id=model_id,
                lifecycle="retired",
                created_at=dt.datetime(1970, 1, 1, tzinfo=dt.UTC),
                display_name=alias,
            ), False
        if model.lifecycle != "active":
            return model, True

        # The Models API can lag behind published SDK deprecations.
        retirement_date = DEPRECATED_MODELS.get(
            model_id, DEPRECATED_MODELS.get(model.id)
        )
        if retirement_date is None:
            return model, True
        retires_at = _parse_sdk_retirement_date(retirement_date)
        return model.model_copy(
            update={
                "lifecycle": "retired"
                if retires_at is not None and retires_at <= dt_util.utcnow()
                else "deprecated",
                "retires_at": retires_at or model.retires_at,
            }
        ), True
