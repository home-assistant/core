"""Config flow for TheSilentWave integration."""

import logging
from typing import Any

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
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
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            # Check if device is reachable.
            websession = async_get_clientsession(self.hass)
            client = SilentWaveClient(user_input[CONF_HOST], session=websession)

            try:
                await client.get_status()
            except SilentWaveError as err:
                _LOGGER.debug("Device connection check failed: %s", err)
                errors[CONF_HOST] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="TheSilentWave",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )
