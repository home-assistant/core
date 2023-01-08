"""Config flow for Sunsynk integration."""
from __future__ import annotations

import logging
from typing import Any

from sunsynk.client import InvalidCredentialsException, SunsynkClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class SunsynkHub:
    """SunsynkHub - authenticates against Sunsynk API."""

    def __init__(self) -> None:
        """Initialise a config flow for Sunsynk."""
        self.client = None

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            self.client = await SunsynkClient.create(username, password)
            return True
        except InvalidCredentialsException:
            return False

    async def get_inverters(self):
        """Get the list of inverters."""
        if self.client is None:
            return []
        return await self.client.get_inverters()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> SunsynkHub:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = SunsynkHub()

    if not await hub.authenticate(data["username"], data["password"]):
        raise InvalidAuth

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunsynk."""

    VERSION = 1

    username: str | None = None
    password: str | None = None
    hub: SunsynkHub | None = None

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
            self.hub = await validate_input(self.hass, user_input)
            self.username = user_input["username"]
            self.password = user_input["password"]
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self.async_step_inverter()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_inverter(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the inverter selection step."""
        if user_input is None and self.hub is not None:
            inverters = await self.hub.get_inverters()
            options = [
                selector.SelectOptionDict(value=inverter.sn, label=inverter.sn)
                for inverter in inverters
            ]
            inverter_schema = vol.Schema(
                {
                    vol.Required("inverter_sn"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            )
            return self.async_show_form(step_id="inverter", data_schema=inverter_schema)

        assert user_input is not None
        user_input["username"] = self.username
        user_input["password"] = self.password
        return self.async_create_entry(
            title=f"Inverter {user_input['inverter_sn']}", data=user_input
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
