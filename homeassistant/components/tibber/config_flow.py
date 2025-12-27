"""Adds config flow for Tibber integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import tibber
from tibber import data_api as tibber_data_api
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_LEGACY_ACCESS_TOKEN, DATA_API_DEFAULT_SCOPES, DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_LEGACY_ACCESS_TOKEN): str})
ERR_TIMEOUT = "timeout"
ERR_CLIENT = "cannot_connect"
ERR_TOKEN = "invalid_access_token"
TOKEN_URL = "https://developer.tibber.com/settings/access-token"

_LOGGER = logging.getLogger(__name__)


class TibberConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._access_token: str | None = None
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
        if user_input is None:
            data_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA, {CONF_LEGACY_ACCESS_TOKEN: self._access_token or ""}
            )

            return self.async_show_form(
                step_id=SOURCE_USER,
                data_schema=data_schema,
                description_placeholders={"url": TOKEN_URL},
                errors={},
            )

        self._access_token = user_input[CONF_LEGACY_ACCESS_TOKEN].replace(" ", "")
        tibber_connection = tibber.Tibber(
            access_token=self._access_token,
            websession=async_get_clientsession(self.hass),
        )
        self._title = tibber_connection.name or "Tibber"

        errors: dict[str, str] = {}
        try:
            await tibber_connection.update_info()
        except TimeoutError:
            errors[CONF_LEGACY_ACCESS_TOKEN] = ERR_TIMEOUT
        except tibber.InvalidLoginError:
            errors[CONF_LEGACY_ACCESS_TOKEN] = ERR_TOKEN
        except (
            aiohttp.ClientError,
            tibber.RetryableHttpExceptionError,
            tibber.FatalHttpExceptionError,
        ):
            errors[CONF_LEGACY_ACCESS_TOKEN] = ERR_CLIENT

        if errors:
            data_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA, {CONF_LEGACY_ACCESS_TOKEN: self._access_token or ""}
            )

            return self.async_show_form(
                step_id=SOURCE_USER,
                data_schema=data_schema,
                description_placeholders={"url": TOKEN_URL},
                errors=errors,
            )

        await self.async_set_unique_id(tibber_connection.user_id)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_account",
                description_placeholders={"title": reauth_entry.title},
            )
        else:
            self._abort_if_unique_id_configured()

        return await self.async_step_pick_implementation()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth flow."""
        reauth_entry = self._get_reauth_entry()
        self._access_token = reauth_entry.data.get(CONF_LEGACY_ACCESS_TOKEN)
        self._title = reauth_entry.title
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication by reusing the user step."""
        reauth_entry = self._get_reauth_entry()
        self._access_token = reauth_entry.data.get(CONF_LEGACY_ACCESS_TOKEN)
        self._title = reauth_entry.title
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Finalize the OAuth flow and create the config entry."""
        if self._access_token is None:
            return self.async_abort(reason="missing_configuration")

        data[CONF_LEGACY_ACCESS_TOKEN] = self._access_token

        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        data_api_client = tibber_data_api.TibberDataAPI(
            access_token,
            websession=async_get_clientsession(self.hass),
        )

        try:
            await data_api_client.get_userinfo()
        except (aiohttp.ClientError, TimeoutError):
            return self.async_abort(reason="cannot_connect")

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry,
                data=data,
                title=self._title,
            )

        return self.async_create_entry(title=self._title, data=data)
