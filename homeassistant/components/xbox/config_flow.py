"""Config flow for xbox."""

from collections.abc import Mapping
import logging
from typing import Any

from httpx import AsyncClient
from pythonxbox.api.client import XboxLiveClient
from pythonxbox.authentication.manager import AuthenticationManager
from pythonxbox.authentication.models import OAuth2TokenResponse

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle xbox OAuth2 authentication."""

    DOMAIN = DOMAIN

    MINOR_VERSION = 2

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["Xboxlive.signin", "Xboxlive.offline_access"]
        return {"scope": " ".join(scopes)}

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
