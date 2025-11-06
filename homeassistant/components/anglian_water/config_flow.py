"""Config flow for the Anglian Water integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import CookieJar
import jwt
from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.exceptions import (
    SelfAssertedError,
    ServiceUnavailableError,
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
        vol.Optional(CONF_ACCOUNT_NUMBER): selector.TextSelector(),
    }
)


class AnglianWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anglian Water."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            auth = MSOB2CAuth(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=async_create_clientsession(
                    self.hass,
                    cookie_jar=CookieJar(quote_cookie=False),
                ),
            )
            try:
                await auth.send_login_request()
                # The initial implementation won't support cost predictions so default to Anglian area
                await AnglianWater.create_from_authenticator(
                    authenticator=auth, area="Anglian"
                )
            except ServiceUnavailableError:
                errors["base"] = "cannot_connect"
            except SelfAssertedError:
                errors["base"] = "invalid_auth"
            except SmartMeterUnavailableError:
                return self.async_abort(reason="smart_meter_unavailable")
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # decode the access token to get the account number
                decoded_token = jwt.decode(
                    auth.access_token,
                    options={"verify_signature": False, "verify_aud": False},
                )
                account_number = user_input.get(CONF_ACCOUNT_NUMBER) or decoded_token.get("extension_accountNumber")
                await self.async_set_unique_id(account_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=account_number,
                    data={
                        **user_input,
                        CONF_ACCESS_TOKEN: auth.refresh_token,
                        CONF_ACCOUNT_NUMBER: account_number,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
