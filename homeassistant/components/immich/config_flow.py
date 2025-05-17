"""Config flow for the Immich integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aioimmich import Immich
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError
from aioimmich.server.models import ImmichServerAbout
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DEFAULT_USE_SSL, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SSL, default=DEFAULT_USE_SSL): bool,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def check_server_info(
    hass: HomeAssistant, data: dict[str, Any]
) -> ImmichServerAbout:
    """Try to read server info."""
    session = async_get_clientsession(hass, data[CONF_VERIFY_SSL])
    immich = Immich(
        session, data[CONF_API_KEY], data[CONF_HOST], data[CONF_PORT], data[CONF_SSL]
    )
    return await immich.server.async_get_about_info()


class ImmichConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Immich."""

    VERSION = 1

    _name: str
    _current_data: Mapping[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await check_server_info(self.hass, user_input)
            except ImmichUnauthorizedError:
                errors["base"] = "invalid_auth"
            except CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        self._current_data = entry_data
        self._name = entry_data[CONF_HOST]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if user_input is not None:
            try:
                await check_server_info(self.hass, {**self._current_data, **user_input})
            except ImmichUnauthorizedError:
                errors["base"] = "invalid_auth"
            except CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={**self._current_data, **user_input},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"name": self._name},
            errors=errors,
        )
