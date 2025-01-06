"""Config flow for OneDrive."""

import logging
from typing import Any

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import DOMAIN, OAUTH_SCOPES


class OneDriveConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle OneDrive OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH_SCOPES)}

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        auth_provider = BaseBearerTokenAuthenticationProvider(
            access_token_provider=OneDriveConfigFlowAccessTokenProvider(
                str(data[CONF_TOKEN]["access_token"])
            )
        )
        adapter = GraphRequestAdapter(
            auth_provider=auth_provider,
            client=get_async_client(self.hass),
        )

        graph_client = GraphServiceClient(
            request_adapter=adapter,
            scopes=OAUTH_SCOPES,
        )

        try:
            drive = await graph_client.me.drive.get()
        except APIError:
            self.logger.exception("Failed to connect to OneDrive")
            return self.async_abort(reason="connection_error")
        except Exception:
            self.logger.exception("Unknown error")
            return self.async_abort(reason="unknown")

        if drive is None or not drive.id:
            return self.async_abort(reason="no_drive")

        await self.async_set_unique_id(drive.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=DOMAIN, data=data)
