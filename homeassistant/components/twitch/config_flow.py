"""Config flow for Twitch."""
from __future__ import annotations

import logging
from typing import Any

from twitchAPI.twitch import Twitch

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Twitch OAuth2 authentication."""

    DOMAIN = DOMAIN
    _client: Twitch | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": ",".join([scope.value for scope in OAUTH_SCOPES])}

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        client_id = self.flow_impl.__dict__[CONF_CLIENT_ID]
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = "data[CONF_TOKEN][CONF_REFRESH_TOKEN]"

        self._client = await Twitch(
            app_id=client_id,
            authenticate_app=False,
            target_app_auth_scope=OAUTH_SCOPES,
        )
        self._client.auto_refresh_auth = False

        await self.hass.async_add_executor_job(
            self._client.set_user_authentication,
            access_token,
            OAUTH_SCOPES,
            refresh_token,
            True,
        )

        return self.async_abort(reason="yes")
