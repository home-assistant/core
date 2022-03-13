"""Config flow for GL-inet integration."""
from __future__ import annotations

import logging
from typing import Any

from gli_py import GLinet
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

# from homeassistant.helpers import config_validation as cv


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="http://192.168.8.1"): str,
        vol.Required(CONF_PASSWORD, default="goodlife"): str,
    }
)


class TestingHub:
    """Testing class to test connection and authentication."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host: str = host
        self.router: GLinet = GLinet(base_url=self.host + "/cgi-bin/api/", sync=False)
        self.router_model: str = ""
        self.router_mac: str = ""

    async def connect(self) -> bool:
        """Test if we can communicate with the host."""
        try:
            res = await self.router.router_model()
            self.router_model = res["model"]
            return True
        except ConnectionError:
            _LOGGER.error(
                "Failed to connect to %s, is it really a GL-inet router?", self.host
            )
        except TypeError:
            _LOGGER.error(
                "Failed to parse router response to %s, is it the right firmware version?",
                self.host,
            )
        return False

    async def authenticate(self, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            await self.router.async_login(password)
            res = await self.router.router_mac()
            self.router_mac = res["factorymac"]
        except ConnectionRefusedError:
            _LOGGER.error("Failed to authenticate with Gl-inet router during testing")
        return self.router.logged_in


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = TestingHub(data[CONF_HOST])

    if not await hub.connect():
        raise CannotConnect

    if not await hub.authenticate(data[CONF_PASSWORD]):
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {
        "title": "GL-inet " + hub.router_model,
        "mac": hub.router_mac,
        "data": {
            CONF_HOST: data[CONF_HOST],
            CONF_API_TOKEN: hub.router.token,
            CONF_PASSWORD: data[CONF_PASSWORD],
        },
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GL-inet."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            user_input = {}
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}
        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            unique_id: str = format_mac(info["mac"])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=info["data"])

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for GL-inet."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
                    ),
                ): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=900))
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
