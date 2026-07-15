"""Config flow for DVLA integration."""

import logging
from typing import Any, override

from aio_dvla_vehicle_enquiry import DVLAClient, DVLAError, DVLAInvalidRegistrationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_KEY, CONF_REG_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REG_NUMBER): str,
    }
)


class DVLAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DVLA."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reg_number = user_input[CONF_REG_NUMBER].replace(" ", "").upper()
            user_input[CONF_REG_NUMBER] = reg_number

            await self.async_set_unique_id(reg_number)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = DVLAClient(session, API_KEY)

            try:
                await client.async_get_vehicle(reg_number)
            except DVLAInvalidRegistrationError:
                errors["base"] = "invalid_registration"
            except DVLAError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=reg_number,
                    data={CONF_REG_NUMBER: reg_number},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {},
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidRegistration(HomeAssistantError):
    """Error to indicate the registration number is invalid or unknown."""
