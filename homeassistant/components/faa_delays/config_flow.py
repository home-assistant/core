"""Config flow for FAA Delays integration."""

import logging
from typing import Any

from aiohttp import ClientConnectionError
import faadelays
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ID
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_ID): str})


class FAADelaysConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FAA Delays."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ID])
            self._abort_if_unique_id_configured()

            websession = aiohttp_client.async_get_clientsession(self.hass)

            data = faadelays.Airport(user_input[CONF_ID], websession)

            try:
                await data.update()

            except ClientConnectionError:
                _LOGGER.error("Error connecting to FAA API")
                errors["base"] = "cannot_connect"

            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                _LOGGER.debug(
                    "Creating entry with id: %s",
                    user_input[CONF_ID],
                )
                return self.async_create_entry(title=data.code, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
