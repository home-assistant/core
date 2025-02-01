"""Config flow for OneDrive."""

from collections.abc import Mapping
import logging
from typing import Any, cast

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from kiota_abstractions.method import Method
from kiota_abstractions.request_information import RequestInformation
from msgraph import GraphRequestAdapter, GraphServiceClient

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import DOMAIN, OAUTH_SCOPES


class OneDriveConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
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
                cast(str, data[CONF_TOKEN][CONF_ACCESS_TOKEN])
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

        # need to get adapter from client, as client changes it
        request_adapter = cast(GraphRequestAdapter, graph_client.request_adapter)

        request_info = RequestInformation(
            method=Method.GET,
            url_template="{+baseurl}/me/drive/special/approot",
            path_parameters={},
        )
        parent_span = request_adapter.start_tracing_span(request_info, "get_approot")

        # get the OneDrive id
        # use low level methods, to avoid files.read permissions
        # which would be required by drives.me.get()
        try:
            response = await request_adapter.get_http_response_message(
                request_info=request_info, parent_span=parent_span
            )
        except APIError:
            self.logger.exception("Failed to connect to OneDrive")
            return self.async_abort(reason="connection_error")
        except Exception:
            self.logger.exception("Unknown error")
            return self.async_abort(reason="unknown")

        drive: dict = response.json()

        await self.async_set_unique_id(drive["parentReference"]["driveId"])

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            self._abort_if_unique_id_mismatch(
                reason="wrong_drive",
            )
            return self.async_update_reload_and_abort(
                entry=reauth_entry,
                data=data,
            )

        self._abort_if_unique_id_configured()

        user = drive.get("createdBy", {}).get("user", {}).get("displayName")

        title = f"{user}'s OneDrive" if user else "OneDrive"

        return self.async_create_entry(title=title, data=data)

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
