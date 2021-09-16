"""Config flow for Aseko Pool Live integration."""
from __future__ import annotations

import logging
from typing import Any

from aioaseko import APIUnavailable, InvalidAuthCredentials, MobileAccount, WebAccount
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aseko Pool Live."""

    VERSION = 1

    async def get_account_info(self, email: str, password: str) -> dict:
        """Get account info from the mobile API and the web API."""
        session = async_get_clientsession(self.hass)

        web_account = WebAccount(session, email, password)
        try:
            web_account_info = await web_account.login()
        except APIUnavailable as err:
            raise CannotConnect from err
        except InvalidAuthCredentials as err:
            raise InvalidAuth from err

        mobile_account = MobileAccount(session, email, password)
        try:
            await mobile_account.login()
        except APIUnavailable as err:
            raise CannotConnect from err
        except InvalidAuthCredentials as err:
            raise InvalidAuth from err

        return {
            CONF_ACCESS_TOKEN: mobile_account.access_token,
            CONF_EMAIL: web_account_info.email,
            CONF_UNIQUE_ID: web_account_info.user_id,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await self.get_account_info(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_UNIQUE_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["email"],
                    data={CONF_ACCESS_TOKEN: info[CONF_ACCESS_TOKEN]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
