"""Config flow for Discovergy integration."""
from __future__ import annotations

import logging
from typing import Any

import pydiscovergy
import pydiscovergy.error as discovergyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    APP_NAME,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        discovergy_instance = pydiscovergy.Discovergy(
            APP_NAME, data[CONF_EMAIL], data[CONF_PASSWORD]
        )
        access_token = await discovergy_instance.login()

        # store token pairs for later use so we don't need to request new pair each time
        data[CONF_CONSUMER_KEY] = discovergy_instance.consumer_token.key
        data[CONF_CONSUMER_SECRET] = discovergy_instance.consumer_token.secret
        data[CONF_ACCESS_TOKEN] = access_token.token
        data[CONF_ACCESS_TOKEN_SECRET] = access_token.token_secret
    except discovergyError.InvalidLogin:
        raise InvalidAuth
    except discovergyError.HTTPError:
        raise CannotConnect

    return {"title": discovergy_instance.email, "data": data}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discovergy."""

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
            result = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # set unique id to title which is the account email
            await self.async_set_unique_id(result["title"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=result["title"], data=result["data"])

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
