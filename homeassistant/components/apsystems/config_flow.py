"""The config_flow for APsystems local API integration."""

from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from APsystemsEZ1 import APsystemsEZ1M
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT): cv.port,
    }
)


class APsystemsLocalAPIFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Apsystems local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass, False)
            api = APsystemsEZ1M(
                ip_address=user_input[CONF_IP_ADDRESS],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                session=session,
            )
            try:
                device_info = await api.get_device_info()
            except (TimeoutError, ClientConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_info.deviceId)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Solar",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
