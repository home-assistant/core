"""Config flow for IntelliDwell Sprinkler Controller integration."""

import logging
from typing import Any, override

from pyintellidwell import (
    IntelliDwellClient,
    IntelliDwellConnectionError,
    IntelliDwellInvalidResponseError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(client: IntelliDwellClient) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        await client.get_status()
    except (IntelliDwellConnectionError, IntelliDwellInvalidResponseError) as err:
        raise CannotConnect from err
    return {"title": f"IntelliDwell Sprinkler ({client.host})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliDwell Sprinkler Controller."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            self._async_abort_entries_match({CONF_HOST: host})

            try:
                session = async_get_clientsession(self.hass)
                client = IntelliDwellClient(host, session=session)
                info = await validate_input(client)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
