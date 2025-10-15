"""Config flow for TheSilentWave integration."""

import ipaddress
import logging
from typing import Any

import voluptuous as vol

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TheSilentWaveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TheSilentWave integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user input for the configuration."""
        errors = {}

        if user_input is not None:
            # Check for duplicate entries.
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                # Validate IP address.
                ipaddress.ip_address(user_input[CONF_HOST])

                # Check if device is reachable.
                await self._async_check_device(user_input[CONF_HOST])

                return self.async_create_entry(
                    title=f"TheSilentWave",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

            except ValueError:
                _LOGGER.warning("Invalid IP address entered: %s", user_input[CONF_HOST])
                errors[CONF_HOST] = "invalid_ip"
            except ConfigEntryNotReady:
                _LOGGER.warning("Cannot connect to device")
                errors[CONF_HOST] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def _async_check_device(self, host: str) -> None:
        """Check if the device is reachable."""
        websession = async_get_clientsession(self.hass)
        client = SilentWaveClient(host, session=websession)
        try:
            await client.get_status()
        except SilentWaveError as err:
            _LOGGER.debug("Device connection check failed: %s", err)
            raise ConfigEntryNotReady("Cannot connect to device") from err
