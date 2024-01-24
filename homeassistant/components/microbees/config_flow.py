"""Config flow for microBees integration."""
import logging
from typing import Any

from microBeesPy.exceptions import MicroBeesWrongCredentialsException
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_TOKEN,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .microbees import MicroBeesConnector

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for microBees."""

    VERSION = 1

    async def validate_input_sync(self, hass, data):
        """Validate the user input allows us to connect."""
        try:
            hass.data[DOMAIN] = {}
            hass.data[DOMAIN]["connector"] = MicroBeesConnector(
                data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET]
            )
            token = await hass.data[DOMAIN]["connector"].login(
                data[CONF_EMAIL], data[CONF_PASSWORD]
            )
            hass.data[DOMAIN][CONF_TOKEN] = token
        except (ConnectTimeout, HTTPError):
            raise CannotConnect
        except MicroBeesWrongCredentialsException:
            raise InvalidAuth

        return {"title": data[CONF_EMAIL], "access_token": token}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self.validate_input_sync(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    options={CONF_TOKEN: info["access_token"]},
                )

        return self.async_show_form(
            description_placeholders={
                CONF_EMAIL: "Email",
                CONF_PASSWORD: "Password",
                "client_id": "Client Id",
                "client_secret": "Client Secret",
            },
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
