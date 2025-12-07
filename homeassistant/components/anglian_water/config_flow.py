"""Config flow for the Anglian Water integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import CookieJar
from pyanglianwater import AnglianWater
from pyanglianwater.auth import BaseAuth, MSOB2CAuth
from pyanglianwater.exceptions import (
    InvalidAccountIdError,
    SelfAssertedError,
    SmartMeterUnavailableError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_ACCOUNT_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_ACCOUNT_NUMBER): selector.TextSelector(),
    }
)


async def validate_credentials(auth: MSOB2CAuth) -> str | MSOB2CAuth:
    """Validate the provided credentials."""
    try:
        await auth.send_login_request()
    except SelfAssertedError:
        return "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    _aw = AnglianWater(authenticator=auth)
    try:
        await _aw.validate_smart_meter()
    except (InvalidAccountIdError, SmartMeterUnavailableError):
        return "smart_meter_unavailable"
    return auth


class AnglianWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anglian Water."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            validation_response = await validate_credentials(
                MSOB2CAuth(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    session=async_create_clientsession(
                        self.hass,
                        cookie_jar=CookieJar(quote_cookie=False),
                    ),
                    account_number=user_input[CONF_ACCOUNT_NUMBER],
                )
            )
            if isinstance(validation_response, BaseAuth):
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_NUMBER])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_ACCOUNT_NUMBER],
                    data={
                        **user_input,
                        CONF_ACCESS_TOKEN: validation_response.refresh_token,
                    },
                )
            errors["base"] = validation_response

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
