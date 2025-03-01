"""Config flow for Tilt Pi integration."""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TiltPiClient, TiltPiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=1880): int,
    }
)


class TiltPiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tilt Pi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a configuration flow initialized by the user."""

        if user_input is not None:
            await self.async_set_unique_id(f"tiltpi_{user_input[CONF_HOST]}")
            self._abort_if_unique_id_configured()

            errors = {}
            try:
                session = async_get_clientsession(self.hass)
                client = TiltPiClient(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    session=session,
                )
                await client.get_hydrometers()
            except TiltPiError:
                errors["base"] = "cannot_connect"
            except (TimeoutError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=USER_DATA_SCHEMA,
                    errors=errors,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
        )
