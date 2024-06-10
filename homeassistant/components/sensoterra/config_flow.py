"""Config flow for Sensoterra integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from sensoterra.customerapi import CustomerApi, InvalidAuth as StInvalidAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class SensoterraHub:
    """Interfaces to Sensoterra API."""

    def __init__(self) -> None:
        """Initialize."""
        self.token = None

    async def authenticate(self, email: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        api = CustomerApi(email, password)
        expiration = datetime.now() + timedelta(days=365 * 10)
        try:
            self.token = await api.get_token("Home Assistant", "READONLY", expiration)
        except StInvalidAuth as exp:
            _LOGGER.error("Login attempt with %s: %s", email, exp.message)
            return False
        except Exception as exp:
            _LOGGER.error("Unexpected authentication exception")
            raise CannotConnect from exp

        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    hub = SensoterraHub()

    if not await hub.authenticate(data[CONF_EMAIL], data[CONF_PASSWORD]):
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {
        "title": f"Probes of {data[CONF_EMAIL]}",
        "token": hub.token,
    }


class SensoterraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensoterra."""

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
                return self.async_create_entry(
                    title=info["title"], data={"token": info["token"]}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
