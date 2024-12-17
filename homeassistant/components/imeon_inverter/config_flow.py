"""Config flow for Imeon integration."""

import logging
from typing import Any

from imeon_inverter_api.inverter import Inverter
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImeonInverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if entry already exists
            await self.async_set_unique_id(user_input[CONF_ADDRESS])
            self._abort_if_unique_id_configured()

            async with Inverter(user_input[CONF_ADDRESS]) as client:
                try:
                    # Check connection
                    if (
                        await client.login(
                            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                        )
                        is True
                    ):
                        # Create a new configuration entry if login succeeds
                        return self.async_create_entry(
                            title=user_input[CONF_ADDRESS], data=user_input
                        )
                    errors["base"] = "invalid_auth"
                    return self.async_show_form(
                        step_id="user", data_schema=schema, errors=errors
                    )

                except TimeoutError:
                    errors["base"] = "cannot_connect"
                    return self.async_show_form(
                        step_id="user", data_schema=schema, errors=errors
                    )

                except ValueError as e:
                    if "Host invalid" in str(e):
                        errors["base"] = "invalid_host"
                        return self.async_show_form(
                            step_id="user", data_schema=schema, errors=errors
                        )
                    if "Route invalid" in str(e):
                        errors["base"] = "invalid_route"
                        return self.async_show_form(
                            step_id="user", data_schema=schema, errors=errors
                        )
                    errors["base"] = "unknown"
                    return self.async_show_form(
                        step_id="user", data_schema=schema, errors=errors
                    )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
