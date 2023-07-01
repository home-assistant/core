"""Config flow for Komfovent integration."""
from __future__ import annotations

import logging
from typing import Any

import komfovent_api
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PARAM_HOST, PARAM_PASSWORD, PARAM_USERNAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(PARAM_HOST): str,
        vol.Required(PARAM_USERNAME, default="user"): str,
        vol.Required(PARAM_PASSWORD): str,
    }
)

ERRORS_MAP = {"NOT_FOUND": "cannot_connect", "UNAUTHORISED": "invalid_auth"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Komfovent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        conf_host = str(user_input[PARAM_HOST])
        conf_username = str(user_input[PARAM_USERNAME])
        conf_password = str(user_input[PARAM_PASSWORD])

        await self.async_set_unique_id(conf_host)
        self._abort_if_unique_id_configured()

        result = await komfovent_api.check_connection(
            conf_host, conf_username, conf_password
        )
        if result == "SUCCESS":
            return self.async_create_entry(title=conf_host, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": ERRORS_MAP.get(result, "unknown")},
        )
