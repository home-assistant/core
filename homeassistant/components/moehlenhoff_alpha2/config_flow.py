"""Alpha2 config flow."""
import asyncio
import logging

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"host": str})


async def validate_input(data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    base = Alpha2Base(data["host"])
    try:
        await base.update_data()
    except (aiohttp.client_exceptions.ClientConnectorError, asyncio.TimeoutError):
        return {"error": "cannot_connect"}

    # Return info that you want to store in the config entry.
    return {"title": base.name}


class Alpha2BaseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Möhlenhoff Alpha2 config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                for entry in self._async_current_entries(include_ignore=False):
                    if entry.data["host"] == user_input["host"]:
                        return self.async_abort(reason="already_configured")

                result = await validate_input(user_input)
                if result.get("error"):
                    errors["base"] = result["error"]
                else:
                    return self.async_create_entry(
                        title=result["title"], data=user_input
                    )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
