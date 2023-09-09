"""Config flow for Komfovent integration."""
from __future__ import annotations

import logging
from typing import Any

import komfovent_api
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER = "user"
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME, default="user"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

ERRORS_MAP = {
    komfovent_api.KomfoventConnectionResult.NOT_FOUND: "cannot_connect",
    komfovent_api.KomfoventConnectionResult.UNAUTHORISED: "invalid_auth",
    komfovent_api.KomfoventConnectionResult.INVALID_INPUT: "invalid_input",
}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Komfovent."""

    VERSION = 1

    def __return_error(
        self, result: komfovent_api.KomfoventConnectionResult
    ) -> FlowResult:
        return self.async_show_form(
            step_id=STEP_USER,
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": ERRORS_MAP.get(result, "unknown")},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id=STEP_USER, data_schema=STEP_USER_DATA_SCHEMA
            )

        conf_host = user_input[CONF_HOST]
        conf_username = user_input[CONF_USERNAME]
        conf_password = user_input[CONF_PASSWORD]

        result, credentials = komfovent_api.get_credentials(
            conf_host, conf_username, conf_password
        )
        if result != komfovent_api.KomfoventConnectionResult.SUCCESS:
            return self.__return_error(result)

        result, settings = await komfovent_api.get_settings(credentials)
        if result != komfovent_api.KomfoventConnectionResult.SUCCESS:
            return self.__return_error(result)

        await self.async_set_unique_id(settings.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=settings.name, data=user_input)
