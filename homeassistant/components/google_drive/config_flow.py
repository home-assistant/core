"""Config flow for Google integration."""
from __future__ import annotations

import logging
from typing import Any

from google.oauth2.credentials import Credentials
from gspread import Client

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_ACCESS, DEFAULT_NAME, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Drive OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": DEFAULT_ACCESS,
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        service = Client(Credentials(data[CONF_TOKEN][CONF_ACCESS_TOKEN]))
        doc = await self.hass.async_add_executor_job(service.create, "Home Assistant")
        await self.async_set_unique_id(doc.id)
        return self.async_create_entry(title=DEFAULT_NAME, data=data)
