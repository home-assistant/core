"""Config flow for YouTube integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from . import AsyncConfigEntryAuth
from .const import AUTH, CONF_CHANNELS, DEFAULT_ACCESS, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] = {}

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> YouTubeOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YouTubeOptionsFlowHandler(config_entry)

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

        service = build(
            "youtube",
            "v3",
            credentials=Credentials(data[CONF_TOKEN][CONF_ACCESS_TOKEN]),
        )
        # pylint: disable=no-member
        own_channel_request: HttpRequest = service.channels().list(
            part="snippet", mine=True
        )
        response = await self.hass.async_add_executor_job(own_channel_request.execute)
        user_id = response["items"][0]["id"]
        self._data = data

        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            return await self.async_step_channels()

        if self.reauth_entry.unique_id == user_id:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_abort(
            reason="wrong_account",
            description_placeholders={
                "title": response["items"][0]["snippet"]["title"]
            },
        )

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which channels to track."""
        service = build(
            "youtube",
            "v3",
            credentials=Credentials(self._data[CONF_TOKEN][CONF_ACCESS_TOKEN]),
        )
        if user_input:
            # pylint: disable=no-member
            own_channel_request: HttpRequest = service.channels().list(
                part="snippet", mine=True
            )
            response = await self.hass.async_add_executor_job(
                own_channel_request.execute
            )
            return self.async_create_entry(
                title=response["items"][0]["snippet"]["title"],
                data=self._data,
                options=user_input,
            )
        # pylint: disable=no-member
        subscription_request: HttpRequest = service.subscriptions().list(
            part="snippet", mine=True, maxResults=50
        )
        response = await self.hass.async_add_executor_job(subscription_request.execute)
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


class YouTubeOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """YouTube Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data=user_input,
            )
        auth: AsyncConfigEntryAuth = self.hass.data[DOMAIN][self.config_entry.entry_id][
            AUTH
        ]
        service = await auth.get_resource()
        # pylint: disable=no-member
        subscription_request: HttpRequest = service.subscriptions().list(
            part="snippet", mine=True, maxResults=50
        )
        response = await self.hass.async_add_executor_job(subscription_request.execute)
        selectable_channels = [
            SelectOptionDict(
                value=subscription["snippet"]["resourceId"]["channelId"],
                label=subscription["snippet"]["title"],
            )
            for subscription in response["items"]
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_CHANNELS): SelectSelector(
                            SelectSelectorConfig(
                                options=selectable_channels, multiple=True
                            )
                        ),
                    }
                ),
                self.options,
            ),
        )
