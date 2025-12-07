"""Config flow for the ENVERTECH EVT800 integration."""

from typing import Any

import pyenvertechevt800
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_TYPE
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DOMAIN, TYPE_TCP_SERVER_MODE

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class EnvertechFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Envertech EVT800."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {
            CONF_IP_ADDRESS: vol.UNDEFINED,
            CONF_PORT: DEFAULT_PORT,
            CONF_TYPE: TYPE_TCP_SERVER_MODE,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step in config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )
            self._data[CONF_IP_ADDRESS] = user_input[CONF_IP_ADDRESS]
            self._data[CONF_PORT] = user_input[CONF_PORT]
            self._data[CONF_TYPE] = TYPE_TCP_SERVER_MODE

            evt800 = pyenvertechevt800.EnvertechEVT800(
                user_input[CONF_IP_ADDRESS], user_input[CONF_PORT]
            )

            canConnect = await evt800.test_connection()

            if not canConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title="Envertech EVT800", data=self._data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA_DEVICE,
            errors=errors,
        )
