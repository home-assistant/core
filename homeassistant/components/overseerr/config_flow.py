"""Config flow for Overseerr integration."""
from __future__ import annotations

import logging
from typing import Any

from overseerr_api import ApiClient, AuthApi, Configuration, User
from overseerr_api.exceptions import OpenApiException
from urllib3.exceptions import MaxRetryError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class OverseerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overseerr."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user-initiated config flow."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            try:
                await self.hass.async_add_executor_job(self.validate_input, user_input)
            except (OpenApiException, MaxRetryError) as exception:
                _LOGGER.error("Error connecting to the Overseerr API: %s", exception)
                errors = {"base": "open_api_exception"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception")
                errors = {"base": "unknown"}
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = self.add_suggested_values_to_schema(USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def validate_input(self, data: dict[str, Any]) -> User | None:
        """Validate the user input allows us to connect to Overseerr."""
        overseerr_config = Configuration(
            api_key={"apiKey": data.get(CONF_API_KEY, "")},
            host=data[CONF_URL],
        )

        overseerr_client = ApiClient(overseerr_config)
        auth_api = AuthApi(overseerr_client)

        return auth_api.auth_me_get()
