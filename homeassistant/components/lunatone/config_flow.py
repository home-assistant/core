"""Config flow for Lunatone."""

import logging
from typing import Any

import aiohttp
from lunatone_dali_api_client import Auth, Info
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LunatoneDALIIoTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone DALI IoT config flow."""

    VERSION = 0
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            auth = Auth(
                session=async_get_clientsession(self.hass),
                base_url=user_input[CONF_URL],
            )
            info = Info(auth)
            try:
                await info.async_update()
            except aiohttp.ClientConnectionError:
                _LOGGER.debug(
                    (
                        "Failed to connect to device %s. Check the URL and if the "
                        "device is connected to power"
                    ),
                    user_input[CONF_URL],
                )
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"lunatone-{info.data.device.serial}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"DALI IoT Gateway {user_input[CONF_URL].split("//")[1]}",
                    data={CONF_URL: user_input[CONF_URL]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL): str}),
            errors=errors,
        )
