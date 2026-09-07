"""Config flow for YouTube integration."""

from collections.abc import Mapping
import logging
from types import MappingProxyType
from typing import Any, override

import voluptuous as vol
from youtubeaio.types import AuthScope, ForbiddenError
from youtubeaio.youtube import YouTube

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CHANNEL_CREATION_HELP_URL,
    CONF_CHANNEL_ID,
    CONF_CHANNELS,
    DEFAULT_ACCESS,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_CHANNEL,
)
from .coordinator import YouTubeConfigEntry


async def async_get_channel_options(
    hass: HomeAssistant, token: str
) -> tuple[list[SelectOptionDict], dict[str, str], bool]:
    """List the channels the user can track.

    Returns the selectable options, a mapping of channel id to title, and
    whether the user has their own channel.
    """
    youtube = YouTube(session=async_get_clientsession(hass))
    await youtube.set_user_authentication(token, [AuthScope.READ_ONLY])

    own_channels = [
        channel
        async for channel in youtube.get_user_channels()
        if channel.snippet is not None
    ]
    subscriptions = [
        subscription
        async for subscription in youtube.get_user_subscriptions()
        if subscription.snippet is not None
    ]

    selectable_channels = [
        SelectOptionDict(
            value=channel.channel_id,
            label=f"{channel.snippet.title} (Your Channel)",
        )
        for channel in own_channels
    ]
    selectable_channels.extend(
        SelectOptionDict(
            value=subscription.snippet.channel_id,
            label=subscription.snippet.title,
        )
        for subscription in subscriptions
    )
    channel_titles = {
        subscription.snippet.channel_id: subscription.snippet.title
        for subscription in subscriptions
    } | {channel.channel_id: channel.snippet.title for channel in own_channels}
    return selectable_channels, channel_titles, bool(own_channels)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    VERSION = 2

    _data: dict[str, Any] = {}
    _title: str = ""
    _channel_titles: dict[str, str] = {}

    DOMAIN = DOMAIN

    _youtube: YouTube | None = None

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_CHANNEL: ChannelFlowHandler}

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
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

    @override
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
            self._channel_titles = {
                channel_id: self._channel_titles.get(channel_id, channel_id)
                for channel_id in dict.fromkeys(user_input[CONF_CHANNELS])
            }
            return self.async_create_entry(title=self._title, data=self._data)
        (
            selectable_channels,
            channel_titles,
            has_own_channel,
        ) = await async_get_channel_options(
            self.hass, self._data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        if not has_own_channel:
            return self.async_abort(
                reason="no_channel",
                description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
            )
        self._channel_titles = channel_titles
        if not selectable_channels:
            return self.async_abort(reason="no_subscriptions")
        return self.async_show_form(
            step_id="channels",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNELS): SelectSelector(
                        SelectSelectorConfig(
                            options=selectable_channels,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    @override
    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Create a subentry for each channel selected in the initial flow."""
        entry: ConfigEntry = result["result"]
        for channel_id, title in self._channel_titles.items():
            self.hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType({CONF_CHANNEL_ID: channel_id}),
                    subentry_type=SUBENTRY_TYPE_CHANNEL,
                    title=title,
                    unique_id=channel_id,
                ),
            )
        return result


class ChannelFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding a channel."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a channel."""
        if user_input is not None:
            return await self._async_create_entry(user_input[CONF_CHANNEL_ID])
        config_entry: YouTubeConfigEntry = self._get_entry()
        try:
            (
                selectable_channels,
                _channel_titles,
                _has_own_channel,
            ) = await async_get_channel_options(
                self.hass, config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
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

        configured = self._async_configured_channel_ids()
        options: list[SelectOptionDict] = []
        seen: set[str] = set()
        for option in selectable_channels:
            if option["value"] in seen or option["value"] in configured:
                continue
            seen.add(option["value"])
            options.append(option)
        if not options:
            return self.async_abort(reason="no_subscriptions")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNEL_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
        )

    @callback
    def _async_configured_channel_ids(self) -> set[str]:
        """Return channel ids already tracked in this Home Assistant instance."""
        configured: set[str] = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id:
                configured.add(entry.unique_id)
            configured |= {
                subentry.unique_id
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_CHANNEL)
                if subentry.unique_id
            }
        return configured

    async def _async_create_entry(self, channel_id: str) -> SubentryFlowResult:
        """Create a subentry for the selected channel."""
        if channel_id in self._async_configured_channel_ids():
            return self.async_abort(reason="already_configured")
        config_entry: YouTubeConfigEntry = self._get_entry()
        youtube = YouTube(session=async_get_clientsession(self.hass))
        await youtube.set_user_authentication(
            config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN], [AuthScope.READ_ONLY]
        )
        try:
            channels = [channel async for channel in youtube.get_channels([channel_id])]
        except ForbiddenError as ex:
            error = ex.args[0]
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception as ex:  # noqa: BLE001
            LOGGER.error("Unknown error occurred: %s", ex.args)
            return self.async_abort(reason="unknown")
        title = channel_id
        if channels and channels[0].snippet is not None:
            title = channels[0].snippet.title
        return self.async_create_entry(
            title=title, data={CONF_CHANNEL_ID: channel_id}, unique_id=channel_id
        )
