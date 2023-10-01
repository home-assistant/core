"""Config flow for Twitch."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, InvalidTokenException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_CHANNELS, CONF_REFRESH_TOKEN, DOMAIN, LOGGER, OAUTH_SCOPES


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
        user = await first(client.get_users())
        assert user

        user_id = user.id

        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            channels = [
                channel.broadcaster_login
                async for channel in await client.get_followed_channels(user_id)
            ]

            return self.async_create_entry(
                title=user.display_name, data=data, options={CONF_CHANNELS: channels}
            )

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
