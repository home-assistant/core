"""Config flow for BlueCurrent integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bluecurrent_api import Client
from bluecurrent_api.exceptions import (
    AlreadyConnected,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


async def validate_input(client: Client, api_token: str) -> None:
    """Validate the user input allows us to connect."""
    await client.validate_api_token(api_token)


async def get_email(client: Client) -> str:
    """Validate the user input allows us to connect."""
    email: str = await client.get_email()
    return email


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Blue Current."""

    VERSION = 1

    input: dict[str, Any] = {}
    client = Client()
    entry: config_entries.ConfigEntry | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:

            api_token = user_input[CONF_API_TOKEN]
            self._async_abort_entries_match({CONF_API_TOKEN: api_token})

            try:
                await validate_input(self.client, api_token)
                email = await get_email(self.client)
            except WebsocketException:
                errors["base"] = "cannot_connect"
            except RequestLimitReached:
                errors["base"] = "limit_reached"
            except AlreadyConnected:
                errors["base"] = "already_connected"
            except InvalidApiToken:
                errors["base"] = "invalid_token"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:

                self.entry = await self.async_set_unique_id(email)
                self.input[CONF_API_TOKEN] = api_token

                if self.entry:
                    await self.update_entry()
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_API_TOKEN][:5], data=self.input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    async def update_entry(self) -> None:
        """Update the config entry."""
        assert self.entry
        self.hass.config_entries.async_update_entry(
            self.entry, data=self.input, title=self.input["api_token"][:5]
        )
        await self.hass.config_entries.async_reload(self.entry.entry_id)
