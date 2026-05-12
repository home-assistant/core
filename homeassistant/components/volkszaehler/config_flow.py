"""Config flow for Volkszaehler integration."""

import logging
from typing import Any

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import (
    VolkszaehlerApiConnectionError,
    VolkszaehlerNoDataAvailable,
)
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_UUID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = Volkszaehler(
        async_get_clientsession(hass),
        data[CONF_UUID],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )
    await api.get_data()


class VolkszaehlerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Volkszaehler."""

    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Set the config entry up from yaml."""
        await self.async_set_unique_id(import_data[CONF_UUID])
        self._abort_if_unique_id_configured()
        title = import_data.get(CONF_NAME, import_data[CONF_UUID])
        import_data.pop(CONF_NAME, None)
        return self.async_create_entry(title=title, data=import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_UUID])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, user_input)
            except VolkszaehlerApiConnectionError:
                errors["base"] = "cannot_connect"
            except VolkszaehlerNoDataAvailable:
                errors["base"] = "no_data"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_UUID], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
