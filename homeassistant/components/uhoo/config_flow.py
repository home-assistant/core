"""Custom uhoo config flow setup."""

from typing import Any

from uhooapi import Client
from uhooapi.errors import UhooError, UnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class UhooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for uHoo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            session = async_create_clientsession(self.hass)
            client = Client(user_input[CONF_API_KEY], session, debug=True)
            try:
                await client.login()
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except UhooError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                key_snippet = user_input[CONF_API_KEY][-5:]
                return self.async_create_entry(
                    title=f"uHoo ({key_snippet})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
