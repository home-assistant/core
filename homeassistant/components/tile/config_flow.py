"""Config flow to configure the Tile integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytile import async_login
from pytile.errors import InvalidAuthError, TileError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, LOGGER

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TileFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Tile config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._password: str | None = None
        self._username: str | None = None

    async def _async_verify(self, step_id: str, schema: vol.Schema) -> ConfigFlowResult:
        """Attempt to authenticate the provided credentials."""
        assert self._username
        assert self._password

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await async_login(self._username, self._password, session=session)
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except TileError as err:
            LOGGER.error("Unknown Tile error: %s", err)
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id=step_id, data_schema=schema, errors=errors
            )

        data = {CONF_USERNAME: self._username, CONF_PASSWORD: self._password}

        if existing_entry := await self.async_set_unique_id(self._username):
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=self._username, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_REAUTH_SCHEMA
            )

        self._password = user_input[CONF_PASSWORD]

        return await self._async_verify("reauth_confirm", STEP_REAUTH_SCHEMA)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_verify("user", STEP_USER_SCHEMA)
