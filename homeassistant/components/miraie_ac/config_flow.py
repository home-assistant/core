"""Config flow for MirAIe AC integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from py_miraie_ac import (
    AuthException,
    AuthType,
    ConnectionException,
    MirAIeAPI,
    MobileNotRegisteredException,
)
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONFIG_KEY_USER_ID, COUNTRY_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_KEY_USER_ID): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    login_id = data[CONFIG_KEY_USER_ID]
    password = data[CONF_PASSWORD]

    if not _validate_mobile_number(login_id):
        raise ValidationError()

    async with MirAIeAPI(
        auth_type=AuthType.MOBILE, login_id=login_id, password=password
    ) as api:
        _LOGGER.debug("Initializing MirAIe API")
        await api.initialize()
        _LOGGER.debug("Connection successful!")

        # Return info that you want to store in the config entry.
        return {"title": f"MirAIe ({login_id})"}


def _validate_mobile_number(mobile_number):
    pattern = r"^\+91\d{10}$"
    match = re.match(pattern, mobile_number)
    return match is not None


def _add_country_code(phone_number):
    if not phone_number.startswith(COUNTRY_CODE):
        return COUNTRY_CODE + phone_number
    return phone_number


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MirAIe AC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                phone_number = user_input[CONFIG_KEY_USER_ID]
                formatted_phone_number = _add_country_code(phone_number)
                user_input[CONFIG_KEY_USER_ID] = formatted_phone_number

                await self.async_set_unique_id(formatted_phone_number)
                self._abort_if_unique_id_configured()

                info = await validate_input(self.hass, user_input)
            except AuthException:
                _LOGGER.error("Invalid user ID or password")
                errors["base"] = "invalid_auth"
            except ValidationError:
                _LOGGER.error("Invalid Mobile Number")
                errors["base"] = "invalid_mobile"
            except ConnectionException:
                _LOGGER.error("Error connecting to the MirAIe services")
                errors["base"] = "cannot_connect"
            except MobileNotRegisteredException:
                _LOGGER.error("Mobile number not registered with MirAIe")
                errors["base"] = "mobile_not_registered"
            except data_entry_flow.AbortFlow:
                _LOGGER.error("Mobile number is already configured in Home Assistant")
                raise
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class ValidationError(HomeAssistantError):
    """Error to indicate that the given input is invalid."""
