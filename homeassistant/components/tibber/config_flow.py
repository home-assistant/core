"""Adds config flow for Tibber integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import tibber
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    async_get_implementations,
)

from .const import AUTH_IMPLEMENTATION, DATA_API_DEFAULT_SCOPES, DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
ERR_TIMEOUT = "timeout"
ERR_CLIENT = "cannot_connect"
ERR_TOKEN = "invalid_access_token"
TOKEN_URL = "https://developer.tibber.com/settings/access-token"

_LOGGER = logging.getLogger(__name__)


class TibberConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    VERSION = 1
    MINOR_VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._access_token = None
        self._title = ""

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data appended to the authorize URL."""
        return {
            **super().extra_authorize_data,
            "scope": " ".join(DATA_API_DEFAULT_SCOPES),
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            tibber_connection = tibber.Tibber(
                access_token=access_token,
                websession=async_get_clientsession(self.hass),
            )

            errors = {}

            try:
                await tibber_connection.update_info()
            except TimeoutError:
                errors[CONF_ACCESS_TOKEN] = ERR_TIMEOUT
            except tibber.InvalidLoginError:
                errors[CONF_ACCESS_TOKEN] = ERR_TOKEN
            except (
                aiohttp.ClientError,
                tibber.RetryableHttpExceptionError,
                tibber.FatalHttpExceptionError,
            ):
                errors[CONF_ACCESS_TOKEN] = ERR_CLIENT

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    description_placeholders={"url": TOKEN_URL},
                    errors=errors,
                )

            await self.async_set_unique_id(tibber_connection.user_id)

            if self.source == SOURCE_REAUTH:
                reauth_entry = self._get_reauth_entry()
                self._abort_if_unique_id_mismatch(
                    reason="wrong_account",
                    description_placeholders={"email": reauth_entry.unique_id or ""},
                )
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_ACCESS_TOKEN: access_token},
                    title=tibber_connection.name,
                )

            self._abort_if_unique_id_configured()
            self._async_abort_entries_match({AUTH_IMPLEMENTATION: DOMAIN})
            self._access_token = access_token
            self._title = tibber_connection.name
            if not await async_get_implementations(self.hass, self.DOMAIN):
                return self.async_abort(reason="missing_credentials")

            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="user" if self.source != SOURCE_REAUTH else "reauth_confirm",
            data_schema=DATA_SCHEMA,
            description_placeholders={"url": TOKEN_URL},
            errors={},
        )

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Finalize the OAuth flow and create the config entry."""
        data[CONF_ACCESS_TOKEN] = self._access_token
        return self.async_create_entry(title=self._title, data=data)
