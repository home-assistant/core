"""Config flow for JustNimbus integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import justnimbus
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.helpers import config_validation as cv

from .const import CONF_ZIP_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_ZIP_CODE): cv.string,
    },
)


class JustNimbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JustNimbus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        unique_id = f"{user_input[CONF_CLIENT_ID]}{user_input[CONF_ZIP_CODE]}"
        await self.async_set_unique_id(unique_id=unique_id)
        if self.source != SOURCE_REAUTH:
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
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if self.source != SOURCE_REAUTH:
                return self.async_create_entry(title="JustNimbus", data=user_input)
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=user_input, unique_id=unique_id
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_user()
