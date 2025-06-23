"""Config flow for Lunatone."""

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
from lunatone_dali_api_client import Auth, Info
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LunatoneDALIIoTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Lunatone DALI IoT config flow."""

    VERSION = 0
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.url: str | None = None
        self.name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.url = user_input[CONF_URL]
            self._async_abort_entries_match({CONF_URL: self.url})
            auth = Auth(
                session=async_get_clientsession(self.hass),
                base_url=self.url,
            )
            info = Info(auth)
            try:
                await info.async_update()
            except aiohttp.InvalidUrlClientError:
                _LOGGER.debug(("Invalid URL: %s"), self.url)
                errors["base"] = "invalid_url"
            except aiohttp.ClientConnectionError:
                _LOGGER.debug(
                    (
                        "Failed to connect to device %s. Check the URL and if the "
                        "device is connected to power"
                    ),
                    self.url,
                )
                errors["base"] = "cannot_connect"
            else:
                self.name = info.data.name
                serial_number = info.data.device.serial
                await self.async_set_unique_id(f"lunatone-{serial_number}")
                self._abort_if_unique_id_configured()
                return self._create_entry()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL, default="http://"): cv.string}
            ),
            errors=errors,
        )

    def _create_entry(self) -> ConfigFlowResult:
        """Return a config entry for the flow."""
        assert self.url is not None
        return self.async_create_entry(
            title=f"{self.name or "DALI Gateway"} - {urlparse(self.url).hostname}",
            data={CONF_URL: self.url},
        )
