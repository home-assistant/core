"""Config flow for Cambridge Audio."""

from typing import Any

from aiostreammagic import StreamMagicClient, StreamMagicError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Cambridge Audio configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = StreamMagicClient(host, session)
            try:
                info = await client.get_info()
            except StreamMagicError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info.udn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name,
                    data={CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
