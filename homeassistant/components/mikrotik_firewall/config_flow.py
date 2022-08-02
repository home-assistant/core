"""Config flow for Mikrotik firewall manager integration."""
from __future__ import annotations

import logging
from typing import Any, Mapping

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_HOST,
    CONF_PASS,
    CONF_RULE_ID,
    CONF_RULE_NAME,
    CONF_RULES,
    CONF_USER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

RULE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RULE_ID): cv.string,
        vol.Optional(CONF_RULE_NAME): cv.string,
        vol.Optional("use_this_rule"): cv.boolean,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        # router ip
        vol.Required(CONF_HOST): cv.string,
        # username
        vol.Required(CONF_USER): cv.string,
        # password, can be empty
        vol.Optional(CONF_PASS): cv.string,
    }
)

STEP_RULES = vol.Schema(
    {
        # rules
        vol.Required(CONF_RULES): vol.All(cv.ensure_list, [RULE_SCHEMA])
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True

    async def get_rules(self, rules_filter: str = None) -> list[str]:
        """Get list of firewall rules from router."""
        return ["net_mati", "net_tv", "net_chrome"]


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA
    with values provided by the user.
    """

    # TODO validate the data can be used to set up a connection.
    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    hub = PlaceholderHub(data[CONF_HOST])

    if not await hub.authenticate(data[CONF_USER], data[CONF_PASS]):
        raise InvalidAuth
    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # read available rules from router
    rules = await hub.get_rules()

    # Return info that you want to store in the config entry.
    return {"title": "Mikrotik firewall", "rules": rules}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mikrotik firewall manager."""

    VERSION = 1

    data: Mapping[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """No user input. Show form."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        """ Validate user input """
        errors: dict[str, Any] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if not errors:
            self.data = user_input
            self.data[CONF_RULES] = info[CONF_RULES]
            return await self.async_step_rule()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_rule(self, user_input: dict[str, Any] | None = None):
        """Second step. Select which rules to add to HA."""
        errors: dict[str, Any] = {}

        if user_input is None:
            rules_schema = vol.Schema(
                {
                    #        vol.Optional("rules", default=list(self.data[CONF_RULES]): cv.multi_select(self.data[CONF_RULES])),
                    vol.Optional(CONF_RULE_ID): cv.string,
                    vol.Optional(CONF_RULE_NAME): cv.string,
                }
            )
            return self.async_show_form(
                step_id="rules", data_schema=rules_schema, errors=errors
            )

        if not errors:
            return self.async_create_entry(title="Mikrotik Firewall", data=self.data)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
