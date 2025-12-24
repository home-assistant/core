"""Config flow for xbox."""

from collections.abc import Mapping
import logging
from typing import Any

from httpx import AsyncClient
from pythonxbox.api.client import XboxLiveClient
from pythonxbox.authentication.manager import AuthenticationManager
from pythonxbox.authentication.models import OAuth2TokenResponse
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_XUID, DOMAIN
from .coordinator import XboxConfigEntry


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle xbox OAuth2 authentication."""

    DOMAIN = DOMAIN

    MINOR_VERSION = 3

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["Xboxlive.signin", "Xboxlive.offline_access"]
        return {"scope": " ".join(scopes)}

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"friend": FriendSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""

        async with AsyncClient() as session:
            auth = AuthenticationManager(session, "", "", "")
            auth.oauth = OAuth2TokenResponse(**data["token"])
            await auth.refresh_tokens()

            client = XboxLiveClient(auth)

            me = await client.people.get_friends_by_xuid(client.xuid)

        await self.async_set_unique_id(client.xuid)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(
                description_placeholders={"gamertag": me.people[0].gamertag}
            )

            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()

        config_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in config_entries:
            if client.xuid in {
                subentry.unique_id for subentry in entry.subentries.values()
            }:
                return self.async_abort(reason="already_configured_as_subentry")

        return self.async_create_entry(title=me.people[0].gamertag, data=data)

    async def async_step_reauth(self, _: Mapping[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()


class FriendSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding a friend."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Subentry user flow."""
        config_entry: XboxConfigEntry = self._get_entry()
        if config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="config_entry_not_loaded")

        client = config_entry.runtime_data.status.client
        friends_list = await client.people.get_friends_own()

        if user_input is not None:
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            if user_input[CONF_XUID] in {entry.unique_id for entry in config_entries}:
                return self.async_abort(reason="already_configured_as_entry")
            for entry in config_entries:
                if user_input[CONF_XUID] in {
                    subentry.unique_id for subentry in entry.subentries.values()
                }:
                    return self.async_abort(reason="already_configured")

            return self.async_create_entry(
                title=next(
                    f.gamertag
                    for f in friends_list.people
                    if f.xuid == user_input[CONF_XUID]
                ),
                data={},
                unique_id=user_input[CONF_XUID],
            )

        if not friends_list.people:
            return self.async_abort(reason="no_friends")

        options = [
            SelectOptionDict(
                value=friend.xuid,
                label=friend.gamertag,
            )
            for friend in friends_list.people
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_XUID): SelectSelector(
                            SelectSelectorConfig(options=options)
                        )
                    }
                ),
                user_input,
            ),
        )
