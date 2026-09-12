"""Config flow for Axle Energy."""

from typing import Any, override

from aioaxlevpp import AxleAuthenticationError, AxleClient, AxleError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class AxleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the household's Axle event feed."""

    async def _validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Check a token with the service, including when no event is scheduled."""
        client = AxleClient(
            async_get_clientsession(self.hass), user_input[CONF_API_KEY]
        )
        try:
            await client.get_event()
        except AxleAuthenticationError:
            return {"base": "invalid_auth"}
        except AxleError:
            return {"base": "cannot_connect"}
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the household event feed."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            if not (errors := await self._validate(user_input)):
                return self.async_create_entry(title="Axle Energy", data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=STEP_SCHEMA, errors=errors
        )
