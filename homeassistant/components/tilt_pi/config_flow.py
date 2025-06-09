"""Config flow for Tilt Pi integration."""

import logging
from typing import Any

import aiohttp
from tiltpi import TiltPiClient, TiltPiError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TiltPiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tilt Pi."""

    VERSION = 1

    async def _check_connection(self, host: str, port: int) -> str | None:
        """Check if we can connect to the TiltPi instance."""
        client = TiltPiClient(
            host=host,
            port=port,
            session=async_get_clientsession(self.hass),
        )
        try:
            await client.get_hydrometers()
        except (TiltPiError, TimeoutError, aiohttp.ClientError):
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a configuration flow initialized by the user."""

        errors = {}
        if user_input:
            url = URL(user_input[CONF_URL])
            if (host := url.host) is None:
                errors[CONF_URL] = "invalid_host"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                port = url.port
                assert port
                error = await self._check_connection(host=host, port=port)
                if error:
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title="Tilt Pi",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL): str}),
            errors=errors,
        )
