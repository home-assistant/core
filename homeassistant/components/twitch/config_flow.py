"""Config flow for Twitch."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from twitchAPI.helper import first
from twitchAPI.twitch import Twitch

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from .const import CONF_CHANNELS, DOMAIN, LOGGER, OAUTH_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Twitch OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self.data: dict[str, Any] = {}

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
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        implementation = cast(
            LocalOAuth2Implementation,
            self.flow_impl,
        )

        client = Twitch(
            app_id=implementation.client_id,
            authenticate_app=False,
        )
        client.auto_refresh_auth = False
        await client.set_user_authentication(
            data[CONF_TOKEN][CONF_ACCESS_TOKEN], scope=OAUTH_SCOPES
        )
        user = await first(client.get_users())
        assert user

        user_id = user.id

        await self.async_set_unique_id(user_id)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            channels = [
                channel.broadcaster_login
                async for channel in await client.get_followed_channels(user_id)
            ]

            return self.async_create_entry(
                title=user.display_name, data=data, options={CONF_CHANNELS: channels}
            )

        reauth_entry = self._get_reauth_entry()
        self._abort_if_unique_id_mismatch(
            reason="wrong_account",
            description_placeholders={"title": reauth_entry.title},
        )

        new_channels = reauth_entry.options[CONF_CHANNELS]
        # Since we could not get all channels at import, we do it at the reauth
        # immediately after.
        if "imported" in reauth_entry.data:
            channels = [
                channel.broadcaster_login
                async for channel in await client.get_followed_channels(user_id)
            ]
            options = list(set(channels) - set(new_channels))
            new_channels = [*new_channels, *options]

        return self.async_update_reload_and_abort(
            reauth_entry,
            data=data,
            options={CONF_CHANNELS: new_channels},
        )

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
