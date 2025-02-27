"""Config flow for Imeon integration."""

import logging
from typing import Any

from imeon_inverter_api.inverter import Inverter
import voluptuous as vol

from homeassistant import config_entries
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


class ImeonInverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            connection = False

            async with Inverter(user_input[CONF_ADDRESS]) as client:
                try:
                    # Check connection
                    connection = await client.login(
                        user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                    )

                except TimeoutError:
                    errors["base"] = "cannot_connect"

                except ValueError as e:
                    if "Host invalid" in str(e):
                        errors["base"] = "invalid_host"

                    elif "Route invalid" in str(e):
                        errors["base"] = "invalid_route"

                    else:
                        errors["base"] = "unknown"

                else:
                    if connection:
                        try:
                            # Check if entry already exists
                            serial = await client.get_serial()
                            await self.async_set_unique_id(serial)
                            self._abort_if_unique_id_configured()

                        except TimeoutError:
                            errors["base"] = "cannot_connect"

                        else:
                            # Create a new configuration entry if login succeeds
                            return self.async_create_entry(
                                title=user_input[CONF_ADDRESS], data=user_input
                            )
                    else:
                        errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
