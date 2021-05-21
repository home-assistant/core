"""Alpha2 config flow."""
import asyncio
import logging

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base
import voluptuous as vol

from homeassistant import config_entries, core

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"host": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    base = Alpha2Base(data["host"])
    await base.update_data()

    # Return info that you want to store in the config entry.
    return {"title": base.name}


class Alpha2BaseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Möhlenhoff Alpha2 config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data["host"] == user_input["host"]:
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(title=info["title"], data=user_input)
            except (
                aiohttp.client_exceptions.ClientConnectorError,
                asyncio.TimeoutError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
