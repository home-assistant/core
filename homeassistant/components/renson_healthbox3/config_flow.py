"""Config flow for Renson integration."""
from __future__ import annotations

from typing import Any

from pyhealthbox3.healthbox3 import (
    Healthbox3,
    Healthbox3ApiClientAuthenticationError,
    Healthbox3ApiClientCommunicationError,
    Healthbox3ApiClientError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_API_KEY): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Renson."""

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

        try:
            client = Healthbox3(
                host=user_input[CONF_HOST],
                api_key=user_input[CONF_API_KEY],
                session=async_create_clientsession(self.hass),
            )

            if CONF_API_KEY in user_input:
                await client.async_enable_advanced_api_features()
            else:
                await client.async_validate_connectivity()
        except Healthbox3ApiClientAuthenticationError:
            errors[CONF_API_KEY] = "auth"
        except Healthbox3ApiClientCommunicationError:
            errors["base"] = "connection"
        except Healthbox3ApiClientError:
            errors["base"] = "unknown"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="Renson", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
