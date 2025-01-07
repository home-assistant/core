"""Config flow for OneDrive."""

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.models.drive import Drive

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import CONF_APPROOT_ID, DOMAIN, OAUTH_SCOPES


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

        drive = await self._get_drive(graph_client.me.drive.get)
        approot = await self._get_drive(
            graph_client.drives.by_drive_id(drive.id)
            .special.by_drive_item_id("approot")
            .get
        )

        await self.async_set_unique_id(drive.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DOMAIN, data={**data, CONF_APPROOT_ID: approot.id}
        )

    async def _get_drive(self, func: Callable[[], Awaitable[Drive]]) -> Drive:
        """Wrap getting a drive from MS graph."""
        try:
            drive = await func()
        except APIError as err:
            self.logger.exception("Failed to connect to OneDrive")
            raise AbortFlow(reason="connection_error") from err
        except Exception as err:
            self.logger.exception("Unknown error")
            raise AbortFlow(reason="unknown") from err

        if drive is None or not drive.id:
            raise AbortFlow(reason="no_drive")
        return drive
