"""Config flow for the Gatus integration."""

import logging
from typing import Any, override

from gatus_api.client import GatusClient, GatusClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://gatus.local:8080"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the user input allows us to connect to Gatus.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    url = data[CONF_URL]
    session = async_get_clientsession(hass)

    client = GatusClient(url=url, session=session)

    try:
        await client.get_endpoints_statuses()
    except GatusClientError as err:
        _LOGGER.error("Cannot connect to Gatus instance at %s: %s", url, err)
        raise CannotConnect from err

    return {"title": "Gatus"}


class GatusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gatus."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step when adding the integration via the UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Gatus setup validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the server."""
