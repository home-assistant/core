"""Config flow for Youtube integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_CHANNELS, CONF_UPLOAD_PLAYLIST, DEFAULT_ACCESS, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] | None = None

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(DEFAULT_ACCESS),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        if self.reauth_entry:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        if self._async_current_entries():
            # Config entry already exists, only one allowed.
            return self.async_abort(reason="single_instance_allowed")
        self._data = data

        return await self.async_step_channels()

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which channels to track."""
        if not self._data:
            return self.async_abort(reason="no_data")
        service = build(
            "youtube",
            "v3",
            credentials=Credentials(self._data[CONF_TOKEN][CONF_ACCESS_TOKEN]),
        )
        if user_input:
            channel_request: HttpRequest = service.channels().list(
                part="contentDetails",
                id=",".join(user_input[CONF_CHANNELS]),
                maxResults=50,
            )
            response: dict = await self.hass.async_add_executor_job(
                channel_request.execute
            )
            channels = {
                channel["id"]: {
                    CONF_UPLOAD_PLAYLIST: channel["contentDetails"]["relatedPlaylists"][
                        "uploads"
                    ]
                }
                for channel in response["items"]
            }
            return self.async_create_entry(
                title="YouTube",
                data=self._data,
                options={
                    CONF_CHANNELS: channels,
                },
            )
        subscription_request: HttpRequest = service.subscriptions().list(
            part="snippet", mine=True, maxResults=50
        )
        response = await self.hass.async_add_executor_job(
            subscription_request.execute
        )
        selectable_channels = [
            SelectOptionDict(
                value=subscription["snippet"]["resourceId"]["channelId"],
                label=subscription["snippet"]["title"],
            )
            for subscription in response["items"]
        ]
        return self.async_show_form(
            step_id="channels",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNELS): SelectSelector(
                        SelectSelectorConfig(options=selectable_channels, multiple=True)
                    ),
                }
            ),
        )
