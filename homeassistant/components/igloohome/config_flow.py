"""Config flow for igloohome integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from igloohome_api import Auth, AuthException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if data[CONF_CLIENT_ID] is None:
        raise InvalidAuth
    if data[CONF_CLIENT_SECRET] is None:
        raise InvalidAuth

    try:
        session = aiohttp.ClientSession()
        # response = await session.post(
        #     url=OAUTH2_TOKEN_URL,
        #     auth=aiohttp.BasicAuth(
        #         login=data[CONF_CLIENT_ID], password=data[CONF_CLIENT_SECRET]
        #     ),
        #     data=form,
        # )
        auth = Auth(
            session=session,
            client_id=data[CONF_CLIENT_ID],
            client_secret=data[CONF_CLIENT_SECRET],
        )
        _ = await auth.async_get_access_token()
    except AuthException as e:
        raise InvalidAuth from e
    except Exception as e:
        raise CannotConnect from e
    finally:
        await session.close()

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Client Credentials"}


class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for igloohome."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
