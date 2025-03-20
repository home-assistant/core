"""Config flow for EnergyFlip integration."""

import logging
from typing import Any

from energyflip import EnergyFlip, EnergyFlipConnectionException, EnergyFlipException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class EnergyFlipConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnergyFlip."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        try:
            user_id = await self._validate_input(user_input)
        except EnergyFlipConnectionException as exception:
            _LOGGER.warning(exception)
            errors["base"] = "cannot_connect"
        except EnergyFlipException as exception:
            _LOGGER.warning(exception)
            errors["base"] = "invalid_auth"
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Set user id as unique id
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            # Create entry
            return self.async_create_entry(
                title=user_input[CONF_USERNAME],
                data={
                    CONF_ID: user_id,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        return await self._show_setup_form(user_input, errors)

    async def _show_setup_form(self, user_input, errors=None):
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {}
        )

    async def _validate_input(self, user_input):
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        energyflip = EnergyFlip(username, password)

        # Attempt authentication. If this fails, an EnergyFlipException will be thrown
        await energyflip.authenticate()

        # Request customer overview. This also sets the user id on the client
        await energyflip.customer_overview()

        return energyflip.get_user_id()
