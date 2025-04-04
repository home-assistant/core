"""Config flow for the Pterodactyl integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL

from .api import (
    PterodactylAPI,
    PterodactylAuthorizationError,
    PterodactylConnectionError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:8080"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_API_KEY): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class PterodactylConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pterodactyl."""

    VERSION = 1

    async def async_validate_connection(self, url: str, api_key: str) -> dict[str, str]:
        """Validate the connection to the Pterodactyl server."""
        errors: dict[str, str] = {}
        api = PterodactylAPI(self.hass, url, api_key)

        try:
            await api.async_init()
        except PterodactylAuthorizationError:
            errors["base"] = "invalid_auth"
        except PterodactylConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception occurred during config flow")
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = URL(user_input[CONF_URL]).human_repr()
            api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_URL: url})
            errors = await self.async_validate_connection(url, api_key)

            if not errors:
                return self.async_create_entry(title=url, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform re-authentication on an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that re-authentication is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            url = reauth_entry.data[CONF_URL]
            api_key = user_input[CONF_API_KEY]

            errors = await self.async_validate_connection(url, api_key)

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
