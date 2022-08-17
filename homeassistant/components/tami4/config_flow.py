"""Config flow for edge integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from Tami4EdgeAPI import Tami4EdgeAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_PHONE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_PHONE_NUMBER_SCHEMA = vol.Schema({vol.Required(CONF_PHONE): cv.string})

STEP_OTP_CODE_SCHEMA = vol.Schema({vol.Required("otp"): cv.string})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tami4Edge."""

    VERSION = 1

    phone: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the otp request step."""
        errors = {}
        if user_input is not None:
            self.phone = user_input[CONF_PHONE]

            self.phone = self.phone.replace(" ", "")
            self.phone = self.phone.replace("+9720", "+972")
            self.phone = re.sub("^0", "+972", self.phone)
            self.phone = re.sub("^972", "+972", self.phone)

            try:
                if not re.match(r"^\+972\d{8,9}$", self.phone):
                    raise InvalidPhoneNumber
                await self.hass.async_add_executor_job(
                    Tami4EdgeAPI.request_otp, self.phone
                )
            except InvalidPhoneNumber:
                errors["base"] = "invalid_phone"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=STEP_PHONE_NUMBER_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the otp submission step."""
        errors = {}
        if user_input is not None:
            otp = user_input["otp"]
            try:
                refresh_token = await self.hass.async_add_executor_job(
                    Tami4EdgeAPI.submit_otp, self.phone, otp
                )
                edge = await self.hass.async_add_executor_job(
                    Tami4EdgeAPI, refresh_token
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=edge.device.name, data={"refresh_token": refresh_token}
                )

        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP_CODE_SCHEMA, errors=errors
        )


class InvalidPhoneNumber(HomeAssistantError):
    """Error to indicate that the phone number is invalid."""
