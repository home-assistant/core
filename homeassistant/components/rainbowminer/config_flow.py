"""Config flow for the RainbowMiner integration."""

from typing import Any, override

import probatio
from rainbowminer_api_client import (
    RainbowMinerAuthError,
    RainbowMinerClient,
    RainbowMinerError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_USERNAME): str,
        probatio.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = RainbowMinerClient(
        data[CONF_HOST],
        data[CONF_PORT],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        session=aiohttp_client.async_get_clientsession(hass),
    )
    try:
        await api.get_status()
    except RainbowMinerAuthError as err:
        raise InvalidAuth from err
    except RainbowMinerError as err:
        raise CannotConnect from err
    return {"title": f"RainbowMiner {data[CONF_HOST]}:{data[CONF_PORT]}"}


class RainbowMinerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RainbowMiner."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            match_dict = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
            self._async_abort_entries_match(match_dict)
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                # Recheck, another flow may have created an entry during validation.
                self._async_abort_entries_match(match_dict)
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
