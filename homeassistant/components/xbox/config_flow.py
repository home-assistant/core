"""Config flow for xbox."""

import logging
from typing import Any

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse
from xbox.webapi.common.signed_session import SignedSession

from homeassistant.config_entries import ConfigFlowResult
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

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""

        async with SignedSession() as session:
            auth = AuthenticationManager(session, "", "", "")
            auth.oauth = OAuth2TokenResponse(**data["token"])
            await auth.refresh_tokens()

            client = XboxLiveClient(auth)

            me = await client.people.get_friends_own_batch([client.xuid])
            await self.async_set_unique_id(client.xuid)

        return self.async_create_entry(title=me.people[0].gamertag, data=data)
