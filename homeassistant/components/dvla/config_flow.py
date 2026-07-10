"""Config flow for DVLA integration."""

import logging
from typing import Any, override

from aio_dvla_vehicle_enquiry import DVLAClient, DVLAError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as ConfigFlowBase, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import API_KEY, CONF_REG_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    reg_number = user_input[CONF_REG_NUMBER]

    session = async_get_clientsession(hass)
    client = DVLAClient(session, API_KEY)

    try:
        await client.async_get_vehicle(reg_number)
    except DVLAError as err:
        raise CannotConnect from err

    return {"title": reg_number}


class ConfigFlow(ConfigFlowBase, domain=DOMAIN):
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

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={CONF_REG_NUMBER: reg_number},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REG_NUMBER,
                        default=(
                            user_input.get(CONF_REG_NUMBER, "")
                            if user_input is not None
                            else ""
                        ),
                    ): cv.string,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
