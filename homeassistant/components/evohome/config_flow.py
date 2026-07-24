"""Adds config flow for Evohome integration."""

from typing import Any, override

import evohomeasync2 as ec2
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_LOCATION_IDX, DOMAIN
from .storage import TokenManager

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
        vol.Optional(CONF_LOCATION_IDX, default=0): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


async def validate_api(
    hass: HomeAssistant, username: str, password: str
) -> dict[str, Any]:
    """Validate the API key."""
    errors: dict[str, str] = {}
    token_manager = TokenManager(
        hass,
        username,
        password,
        async_get_clientsession(hass),
    )
    client_v2 = ec2.EvohomeClient(token_manager)
    try:
        await client_v2.update(dont_update_status=True)  # only config for now
    except ec2.EvohomeError:
        errors["base"] = "cannot_connect"

    return errors


class EvohomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Evohome integration."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""

        errors: dict[str, str] = {}

        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            errors = await validate_api(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )
