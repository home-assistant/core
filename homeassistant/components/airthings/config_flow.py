"""Config flow for Airthings integration."""
from __future__ import annotations

import logging
from typing import Any

import airthings
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ID, CONF_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): str,
        vol.Required(CONF_SECRET): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airthings."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "url": (
                        "https://dashboard.airthings.com/integrations/api-integration"
                    ),
                },
            )

        errors = {}

        try:
            await airthings.get_token(
                async_get_clientsession(self.hass),
                user_input[CONF_ID],
                user_input[CONF_SECRET],
            )
        except airthings.AirthingsConnectionError:
            errors["base"] = "cannot_connect"
        except airthings.AirthingsAuthError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_ID])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Airthings", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
