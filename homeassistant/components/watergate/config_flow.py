"""Config flow for Watergate."""

import logging
from typing import override

import probatio
from watergate_local_api.watergate_api import (
    WatergateApiException,
    WatergateLocalApiClient,
)

from homeassistant.components.webhook import async_generate_id as webhook_generate_id
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SONIC = "Sonic"
WATERGATE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_IP_ADDRESS): str,
    }
)


class WatergateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Watergate config flow."""

    async def _async_get_serial_number(
        self, ip_address: str, errors: dict[str, str]
    ) -> str | None:
        """Return the device serial number or record a connection error."""
        watergate_client = WatergateLocalApiClient(
            base_url=self.prepare_ip_address(ip_address),
            session=async_get_clientsession(self.hass),
        )
        try:
            state = await watergate_client.async_get_device_state()
        except WatergateApiException as exception:
            _LOGGER.error("Error connecting to Watergate device: %s", exception)
            errors[CONF_IP_ADDRESS] = "cannot_connect"
            return None
        if state is None:
            _LOGGER.error("Device state returned as None")
            errors[CONF_IP_ADDRESS] = "cannot_connect"
            return None
        return state.serial_number

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            serial_number = await self._async_get_serial_number(
                user_input[CONF_IP_ADDRESS], errors
            )
            if serial_number is not None:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    data={**user_input, CONF_WEBHOOK_ID: webhook_generate_id()},
                    title=SONIC,
                )

        return self.async_show_form(
            step_id="user", data_schema=WATERGATE_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device IP address."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            serial_number = await self._async_get_serial_number(
                user_input[CONF_IP_ADDRESS], errors
            )
            if serial_number is not None:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                WATERGATE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    def prepare_ip_address(self, ip_address: str) -> str:
        """Prepare the IP address for the Watergate device."""
        return ip_address if ip_address.startswith("http") else f"http://{ip_address}"
