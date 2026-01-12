"""Adds config flow for Tibber integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import tibber

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DATA_API_DEFAULT_SCOPES, DOMAIN

ERR_TIMEOUT = "timeout"
ERR_CLIENT = "cannot_connect"
ERR_TOKEN = "invalid_access_token"

_LOGGER = logging.getLogger(__name__)


class TibberConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    VERSION = 1
    DOMAIN = DOMAIN

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication by reusing the user step."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Finalize the OAuth flow and create the config entry."""
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        tibber_connection = tibber.Tibber(
            access_token=access_token,
            websession=async_get_clientsession(self.hass),
        )

        try:
            await tibber_connection.update_info()
        except TimeoutError:
            return self.async_abort(reason=ERR_TIMEOUT)
        except tibber.InvalidLoginError:
            return self.async_abort(reason=ERR_TOKEN)
        except (
            aiohttp.ClientError,
            tibber.RetryableHttpExceptionError,
            tibber.FatalHttpExceptionError,
        ):
            return self.async_abort(reason=ERR_CLIENT)

        await self.async_set_unique_id(tibber_connection.user_id)

        title = tibber_connection.name or "Tibber"
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_account",
                description_placeholders={"title": reauth_entry.title},
            )
            return self.async_update_reload_and_abort(
                reauth_entry,
                data=data,
                title=title,
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
