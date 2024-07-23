"""The config_flow for APsystems local API integration."""

from aiohttp import client_exceptions
from APsystemsEZ1 import APsystemsEZ1M
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


class APsystemsLocalAPIFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Apsystems local."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        session = async_get_clientsession(self.hass, False)

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass, False)
                api = APsystemsEZ1M(user_input[CONF_IP_ADDRESS], session=session)
                device_info = await api.get_device_info()
                await self.async_set_unique_id(device_info.deviceId)
            except (TimeoutError, client_exceptions.ClientConnectionError) as exception:
                LOGGER.warning(exception)
                _errors["base"] = "connection_refused"
            else:
                return self.async_create_entry(
                    title="Solar",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=_errors,
        )
