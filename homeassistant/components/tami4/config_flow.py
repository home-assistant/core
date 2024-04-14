"""Config flow for edge integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from Tami4EdgeAPI import Tami4EdgeAPI, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import CONF_PHONE, CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

_STEP_PHONE_NUMBER_SCHEMA = vol.Schema({vol.Required(CONF_PHONE): cv.string})

_STEP_OTP_CODE_SCHEMA = vol.Schema({vol.Required("otp"): cv.string})
_PHONE_MATCHER = re.compile(r"^(\+?972)?0?(?P<number>\d{8,9})$")


class Tami4ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tami4Edge."""

    VERSION = 1

    phone: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the otp request step."""
        errors = {}
        if user_input is not None:
            phone = user_input[CONF_PHONE].strip()

            try:
                if m := _PHONE_MATCHER.match(phone):
                    self.phone = f"+972{m.group('number')}"
                else:
                    raise InvalidPhoneNumber
                await self.hass.async_add_executor_job(
                    Tami4EdgeAPI.request_otp, self.phone
                )
            except InvalidPhoneNumber:
                errors["base"] = "invalid_phone"
            except exceptions.Tami4EdgeAPIException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=_STEP_PHONE_NUMBER_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the otp submission step."""
        errors = {}
        if user_input is not None:
            otp = user_input["otp"]
            try:
                refresh_token = await self.hass.async_add_executor_job(
                    Tami4EdgeAPI.submit_otp, self.phone, otp
                )
                api = await self.hass.async_add_executor_job(
                    Tami4EdgeAPI, refresh_token
                )
            except exceptions.OTPFailedException:
                errors["base"] = "invalid_auth"
            except exceptions.Tami4EdgeAPIException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=api.device.name, data={CONF_REFRESH_TOKEN: refresh_token}
                )

        return self.async_show_form(
            step_id="otp", data_schema=_STEP_OTP_CODE_SCHEMA, errors=errors
        )


class InvalidPhoneNumber(HomeAssistantError):
    """Error to indicate that the phone number is invalid."""
