"""Config flow for Watergate."""

import logging

import voluptuous as vol
from watergate_local_api.watergate_api import (
    WatergateApiException,
    WatergateLocalApiClient,
)

from homeassistant.components.webhook import async_generate_id as webhook_generate_id
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SONIC = "Sonic"
WATERGATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


class WatergateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Watergate config flow."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            watergate_client = WatergateLocalApiClient(
                self.prepare_ip_address(user_input[CONF_IP_ADDRESS])
            )
            try:
                state = await watergate_client.async_get_device_state()
            except WatergateApiException as exception:
                _LOGGER.error("Error connecting to Watergate device: %s", exception)
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            else:
                if state is None:
                    _LOGGER.error("Device state returned as None")
                    errors[CONF_IP_ADDRESS] = "cannot_connect"
                else:
                    await self.async_set_unique_id(state.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        data={**user_input, CONF_WEBHOOK_ID: webhook_generate_id()},
                        title=SONIC,
                    )

        return self.async_show_form(
            step_id="user", data_schema=WATERGATE_SCHEMA, errors=errors
        )

    def prepare_ip_address(self, ip_address: str) -> str:
        """Prepare the IP address for the Watergate device."""
        return ip_address if ip_address.startswith("http") else f"http://{ip_address}"
