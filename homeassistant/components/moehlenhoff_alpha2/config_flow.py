"""Alpha2 config flow."""
import logging
from typing import Any

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    base = Alpha2Base(data[CONF_HOST])
    try:
        await base.update_data()
    except (aiohttp.client_exceptions.ClientConnectorError, TimeoutError):
        return {"error": "cannot_connect"}
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        return {"error": "unknown"}

    # Return info that you want to store in the config entry.
    return {"title": base.name}


class Alpha2BaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Möhlenhoff Alpha2 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            result = await validate_input(user_input)
            if result.get("error"):
                errors["base"] = result["error"]
            else:
                return self.async_create_entry(title=result["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
