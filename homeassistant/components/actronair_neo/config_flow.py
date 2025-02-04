"""Setup config flow for Actron Neo integration."""

import logging
from typing import Any

from actron_neo_api import ActronNeoAPI, ActronNeoAPIError, ActronNeoAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from .const import DOMAIN, ERROR_API_ERROR, ERROR_INVALID_AUTH

_LOGGER = logging.getLogger(__name__)

ACTRON_AIR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ActronNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Actron Air Neo."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api = None
        self.ac_systems = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            _LOGGER.debug("Connecting to Actron Neo API")
            try:
                self.api = ActronNeoAPI(
                    username=user_input["username"], password=user_input["password"]
                )
            except ActronNeoAuthError:
                errors["base"] = ERROR_INVALID_AUTH
                return self.async_show_form(
                    step_id="user",
                    data_schema=ACTRON_AIR_SCHEMA,
                    errors=errors,
                )

            assert self.api is not None

            try:
                await self.api.request_pairing_token("HomeAssistant", "ha-instance-id")
                await self.api.refresh_token()
            except ActronNeoAPIError:
                errors["base"] = ERROR_API_ERROR

            systems = await self.api.get_ac_systems()
            self.ac_systems = systems.get("_embedded", {}).get("ac-system", [])

            for system in self.ac_systems:
                serial_number = system["serial"]
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=system["description"],
                    data={
                        CONF_API_TOKEN: self.api.pairing_token,
                        CONF_DEVICE_ID: serial_number,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=ACTRON_AIR_SCHEMA,
            errors=errors,
        )
