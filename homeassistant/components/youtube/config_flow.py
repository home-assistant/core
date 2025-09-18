"""Config flow for YouTube integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from youtubeaio.types import AuthScope, ForbiddenError
from youtubeaio.youtube import YouTube

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CHANNEL_CREATION_HELP_URL,
    CONF_CHANNELS,
    DEFAULT_ACCESS,
    DOMAIN,
    LOGGER,
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] = {}
    _title: str = ""

    DOMAIN = DOMAIN

    _youtube: YouTube | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> YouTubeOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YouTubeOptionsFlowHandler()

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def get_resource(self, token: str) -> YouTube:
        """Get Youtube resource async."""
        if self._youtube is None:
            self._youtube = YouTube(session=async_get_clientsession(self.hass))
            await self._youtube.set_user_authentication(token, [AuthScope.READ_ONLY])
        return self._youtube

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        try:
            youtube = await self.get_resource(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
            own_channels = [
                channel
                async for channel in youtube.get_user_channels()
                if channel.snippet is not None
            ]
            if not own_channels:
                return self.async_abort(
                    reason="no_channel",
                    description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
                )
        except ForbiddenError as ex:
            error = ex.args[0]
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception as ex:  # noqa: BLE001
            LOGGER.error("Unknown error occurred: %s", ex.args)
            return self.async_abort(reason="unknown")
        self._title = own_channels[0].snippet.title
        self._data = data

        await self.async_set_unique_id(own_channels[0].channel_id)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            return await self.async_step_channels()

        self._abort_if_unique_id_mismatch(
            reason="wrong_account",
            description_placeholders={"title": self._title},
        )

        return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which channels to track."""
        if user_input:
            return self.async_create_entry(
                title=self._title,
                data=self._data,
                options=user_input,
            )
        youtube = await self.get_resource(self._data[CONF_TOKEN][CONF_ACCESS_TOKEN])

        # Get user's own channels
        own_channels = [
            channel
            async for channel in youtube.get_user_channels()
            if channel.snippet is not None
        ]
        if not own_channels:
            return self.async_abort(
                reason="no_channel",
                description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
            )

        # Start with user's own channels
        selectable_channels = [
            SelectOptionDict(
                value=channel.channel_id,
                label=f"{channel.snippet.title} (Your Channel)",
            )
            for channel in own_channels
        ]

        # Add subscribed channels
        selectable_channels.extend(
            [
                SelectOptionDict(
                    value=subscription.snippet.channel_id,
                    label=subscription.snippet.title,
                )
                async for subscription in youtube.get_user_subscriptions()
            ]
        )

        if not selectable_channels:
            return self.async_abort(reason="no_subscriptions")
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


class YouTubeOptionsFlowHandler(OptionsFlow):
    """YouTube Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize form."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data=user_input,
            )
        youtube = YouTube(session=async_get_clientsession(self.hass))
        await youtube.set_user_authentication(
            self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN], [AuthScope.READ_ONLY]
        )

        # Get user's own channels
        own_channels = [
            channel
            async for channel in youtube.get_user_channels()
            if channel.snippet is not None
        ]
        if not own_channels:
            return self.async_abort(
                reason="no_channel",
                description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
            )

        # Start with user's own channels
        selectable_channels = [
            SelectOptionDict(
                value=channel.channel_id,
                label=f"{channel.snippet.title} (Your Channel)",
            )
            for channel in own_channels
        ]

        # Add subscribed channels
        selectable_channels.extend(
            [
                SelectOptionDict(
                    value=subscription.snippet.channel_id,
                    label=subscription.snippet.title,
                )
                async for subscription in youtube.get_user_subscriptions()
            ]
        )

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
                self.config_entry.options,
            ),
        )
