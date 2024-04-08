"""Config flow for pyLoad integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import CannotConnect, InvalidAuth, PyLoadAPI
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])
            user_input.pop(CONF_URL, None)
            if host := user_input.get(CONF_HOST):
                port = user_input[CONF_PORT]
                proto = "https" if user_input.get(CONF_SSL) else "http"
                user_input[CONF_URL] = f"{proto}://{host}:{port}/"

            pyload = PyLoadAPI(
                session,
                user_input[CONF_URL],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await pyload.login()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"{host}:{port}", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        assert self.reauth_entry
        username = self.reauth_entry.data[CONF_USERNAME]
        if user_input is not None:
            new_input = self.reauth_entry.data | user_input
            session = async_get_clientsession(self.hass, new_input[CONF_VERIFY_SSL])

            pyload = PyLoadAPI(
                session,
                new_input[CONF_URL],
                new_input[CONF_USERNAME],
                new_input[CONF_PASSWORD],
            )
            try:
                await pyload.login()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected exception")
            else:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=new_input
                )

                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: username},
            errors=errors,
        )
