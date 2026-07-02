"""OAuth2 config flow for the Lepro integration."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from .const import CONF_ACCOUNT, CONF_API_HOST, DOMAIN, OAUTH2_SCOPES, REGION_API_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_ACCOUNT): str})


class LoproOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle the Lepro OAuth2 authorization flow."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._api_host: str | None = None
        self._account: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict:
        """Return extra parameters to include in the authorize request."""
        data: dict = {"scope": quote(OAUTH2_SCOPES, safe=" ")}
        if self._account:
            data[CONF_ACCOUNT] = self._account
        data["source"] = "ha"
        return data

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Collect account email and look up the regional API host."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api_host = await self._async_fetch_api_host(user_input[CONF_ACCOUNT])
            except (aiohttp.ClientError, KeyError):
                _LOGGER.debug(
                    "Failed to fetch region for account %s", user_input[CONF_ACCOUNT]
                )
                errors["base"] = "cannot_connect"
            else:
                self._api_host = api_host
                self._account = user_input[CONF_ACCOUNT]
                self.hass.data.setdefault(DOMAIN, {})["api_host"] = api_host
                return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _async_fetch_api_host(self, account: str) -> str:
        """Call the region API and return the apiHost for the given account."""
        session = async_get_clientsession(self.hass)
        timestamp = str(int(time.time()))
        resp = await session.post(
            REGION_API_URL,
            json={"account": account, "timestamp": timestamp},
        )
        resp.raise_for_status()
        body = await resp.json()
        return "https://" + body["data"]["apiHost"]
        # return "http://192.168.30.3:9999"

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create a config entry after OAuth, storing the resolved API host."""
        assert isinstance(self.flow_impl, LocalOAuth2Implementation)
        await self.async_set_unique_id(self.flow_impl.client_id)
        self._abort_if_unique_id_configured()
        data[CONF_API_HOST] = self._api_host
        data[CONF_ACCOUNT] = self._account
        return self.async_create_entry(title="Lepro", data=data)
