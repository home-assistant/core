"""Config flow for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import logging
from typing import Any

from pysaunum import SaunumClient, SaunumException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]

    client = SaunumClient(host=host)

    try:
        await client.connect()
        # Try to read data to verify communication
        await client.async_get_data()
    finally:
        client.close()


class LeilSaunaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Saunum Leil Sauna Control Unit."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            try:
                await validate_input(user_input)
            except SaunumException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_USER:
                    return self.async_create_entry(
                        title="Saunum",
                        data=user_input,
                    )
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
