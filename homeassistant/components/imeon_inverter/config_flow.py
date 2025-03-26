"""Config flow for Imeon integration."""

import logging
from typing import Any

from imeon_inverter_api.inverter import Inverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ImeonInverterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            async with Inverter(user_input[CONF_ADDRESS]) as client:
                try:
                    # Check connection
                    if await client.login(
                        user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                    ):
                        serial = await client.get_serial()

                    else:
                        errors["base"] = "invalid_auth"

                except TimeoutError:
                    errors["base"] = "cannot_connect"

                except ValueError as e:
                    if "Host invalid" in str(e):
                        errors["base"] = "invalid_host"

                    elif "Route invalid" in str(e):
                        errors["base"] = "invalid_route"

                    else:
                        errors["base"] = "unknown"
                        _LOGGER.exception(
                            "Unexpected error occurred while connecting to the Imeon"
                        )

                if not errors:
                    # Check if entry already exists
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()

                    # Create a new configuration entry if login succeeds
                    return self.async_create_entry(
                        title=user_input[CONF_ADDRESS], data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
