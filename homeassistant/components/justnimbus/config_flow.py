"""Config flow for JustNimbus integration."""
from __future__ import annotations

import logging
from typing import Any

import justnimbus
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_ZIP_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_ZIP_CODE): cv.string,
    },
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JustNimbus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        await self.async_set_unique_id(
            f"{user_input[CONF_CLIENT_ID]}{user_input[CONF_ZIP_CODE]}"
        )
        self._abort_if_unique_id_configured()

        client = justnimbus.JustNimbusClient(
            client_id=user_input[CONF_CLIENT_ID], zip_code=user_input[CONF_ZIP_CODE]
        )
        try:
            await self.hass.async_add_executor_job(client.get_data)
        except justnimbus.InvalidClientID:
            errors["base"] = "invalid_auth"
        except justnimbus.JustNimbusError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="JustNimbus", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
