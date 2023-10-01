"""Config flow for Twitch."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from twitchAPI.helper import first
from twitchAPI.twitch import (
    FollowedChannel,
    Twitch,
    TwitchAPIException,
    TwitchBackendException,
    TwitchUser,
)
from twitchAPI.type import AuthScope, InvalidTokenException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_CHANNELS, CONF_REFRESH_TOKEN, DOMAIN, LOGGER, OAUTH_SCOPES


async def get_followed_channels(
    client: Twitch,
    user: TwitchUser,
) -> list[FollowedChannel]:
    """Return a list of channels the user is following."""
    channels: list[FollowedChannel] = [
        channel
        async for channel in await client.get_followed_channels(
            user_id=user.id,
        )
    ]

    return sorted(
        channels,
        key=lambda channel: channel.broadcaster_name.lower(),
        reverse=False,
    )


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Twitch OAuth2 authentication."""

    DOMAIN = DOMAIN
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self._client: Twitch | None = None
        self._oauth_data: dict[str, Any] = {}
        self._user: TwitchUser | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join([scope.value for scope in OAUTH_SCOPES])}

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> FlowResult:
        """Handle the initial step."""

        client = await Twitch(
            app_id=self.flow_impl.__dict__[CONF_CLIENT_ID],
            authenticate_app=False,
        )
        client.auto_refresh_auth = False
        await client.set_user_authentication(
            data[CONF_TOKEN][CONF_ACCESS_TOKEN], scope=OAUTH_SCOPES
        )

        self._client = client
        self._oauth_data = data

        self._user = await first(client.get_users())
        assert self._user

        user_id = self._user.id

        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            return await self.async_step_channels()

        if self.reauth_entry.unique_id == user_id:
            new_channels = self.reauth_entry.options[CONF_CHANNELS]
            # Since we could not get all channels at import, we do it at the reauth
            # immediately after.
            if "imported" in self.reauth_entry.data:
                channels = [
                    channel.broadcaster_login
                    async for channel in await client.get_followed_channels(user_id)
                ]
                options = list(set(channels) - set(new_channels))
                new_channels = [*new_channels, *options]

            self.hass.config_entries.async_update_entry(
                self.reauth_entry,
                data=data,
                options={CONF_CHANNELS: new_channels},
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_abort(
            reason="wrong_account",
            description_placeholders={"title": self.reauth_entry.title},
        )

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

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import from yaml."""
        client = await Twitch(
            app_id=config[CONF_CLIENT_ID],
            authenticate_app=False,
        )
        client.auto_refresh_auth = False
        token = config[CONF_TOKEN]
        try:
            await client.set_user_authentication(
                token, validate=True, scope=[AuthScope.USER_READ_SUBSCRIPTIONS]
            )
        except InvalidTokenException:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_invalid_token",
                breaks_in_ha_version="2024.4.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_invalid_token",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Twitch",
                },
            )
            return self.async_abort(reason="invalid_token")
        user = await first(client.get_users())
        assert user
        await self.async_set_unique_id(user.id)
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_already_imported",
                breaks_in_ha_version="2024.4.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_already_imported",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Twitch",
                },
            )
            raise err
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Twitch",
            },
        )
        return self.async_create_entry(
            title=user.display_name,
            data={
                "auth_implementation": DOMAIN,
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: token,
                    CONF_REFRESH_TOKEN: "",
                    "expires_at": 0,
                },
                "imported": True,
            },
            options={CONF_CHANNELS: config[CONF_CHANNELS]},
        )

    async def async_step_channels(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle channels step."""
        self.logger.debug("Step channels: %s", user_input)

        self.logger.debug("User: %s", self._user)
        assert self._client
        assert self._user

        if not user_input:
            try:
                channels = await get_followed_channels(
                    self._client,
                    self._user,
                )
            except (TwitchAPIException, TwitchBackendException) as err:
                self.logger.error("Twitch API error: %s", err)
                return self.async_abort(reason="cannot_connect")

            self.logger.debug("Channels: %s", channels)

            return self.async_show_form(
                step_id="channels",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CHANNELS): cv.multi_select(
                            {
                                channel.broadcaster_id: channel.broadcaster_name
                                for channel in channels
                            }
                        ),
                    }
                ),
            )

        return self.async_create_entry(
            title=self._user.display_name,
            data=self._oauth_data,
            options={CONF_CHANNELS: user_input[CONF_CHANNELS]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for GitHub."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle init options flow."""
        return await self.async_step_channels(user_input)

    async def async_step_channels(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle channels options flow."""
        if not user_input:
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    self.hass,
                    self.config_entry,
                )
            )

            configured_channels: list[str] = self.config_entry.options[CONF_CHANNELS]

            client_id = implementation.__dict__[CONF_CLIENT_ID]
            access_token = self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            refresh_token = self.config_entry.data[CONF_TOKEN][CONF_REFRESH_TOKEN]

            client = Twitch(
                app_id=client_id,
                authenticate_app=False,
            )
            client.auto_refresh_auth = False

            await client.set_user_authentication(
                access_token,
                OAUTH_SCOPES,
                refresh_token=refresh_token,
                validate=True,
            )

            user = await first(client.get_users())
            assert user

            channels = await get_followed_channels(
                client,
                user,
            )

            channel_ids = [channel.broadcaster_id for channel in channels]
            channels_dict = {
                channel.broadcaster_id: channel.broadcaster_name for channel in channels
            }

            self.logger.debug("Channels: %s", channels_dict)

            # In case the user has removed a channel that is already tracked
            for channel in configured_channels:
                if channel not in channel_ids:
                    channels_dict[channel] = channel

            return self.async_show_form(
                step_id="channels",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CHANNELS,
                            default=configured_channels,
                        ): cv.multi_select(channels_dict),
                    }
                ),
            )

        return self.async_create_entry(title="", data=user_input)
