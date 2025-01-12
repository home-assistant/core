"""Config flow for OneDrive."""

from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import Any, cast

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.drives.item.items.items_request_builder import (
    ItemsRequestBuilder,
)
from msgraph.generated.models.drive import Drive
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.folder import Folder

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigFlowAccessTokenProvider
from .const import DOMAIN, OAUTH_SCOPES
from .util import get_backup_folder_name


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
                cast(str, data[CONF_TOKEN]["access_token"])
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

        # get the OneDrive id
        drive_id, drive = await self._get_drive_or_drive_item_id(
            graph_client.me.drive.get
        )
        await self.async_set_unique_id(drive_id)

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

        # get the app folder (creates it if it doesn't exist)
        approot_id, _ = await self._get_drive_or_drive_item_id(
            graph_client.drives.by_drive_id(drive_id)
            .special.by_drive_item_id("approot")
            .get
        )

        # get the backup folder and create it if it doesn't exist
        backup_folder_name = await get_backup_folder_name(self.hass)
        items = graph_client.drives.by_drive_id(drive_id).items
        try:
            await items.by_drive_item_id(f"{approot_id}:/{backup_folder_name}:").get()
        except APIError as err:
            if err.response_status_code != 404:
                self.logger.exception("Failed to get backup folder")
                return self.async_abort(reason="connection_error")
            await self._create_backup_folder(items, approot_id, backup_folder_name)

        # try to get title from drive owner
        title = DOMAIN
        drive = cast(Drive, drive)
        if (
            drive is not None
            and drive.owner is not None
            and drive.owner.user is not None
            and drive.owner.user.display_name is not None
        ):
            title = f"{drive.owner.user.display_name}'s OneDrive"

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

    async def _get_drive_or_drive_item_id(
        self,
        func: Callable[[], Awaitable[DriveItem | Drive | None]],
    ) -> tuple[str, Drive | DriveItem]:
        """Get drive or drive item id."""
        try:
            item = await func()
        except APIError as err:
            self.logger.exception("Failed to connect to OneDrive")
            raise AbortFlow(reason="connection_error") from err
        except Exception as err:
            self.logger.exception("Unknown error")
            raise AbortFlow(reason="unknown") from err

        if item is None or not item.id:
            raise AbortFlow(reason="no_drive")
        return item.id, item

    async def _create_backup_folder(
        self, items: ItemsRequestBuilder, base_folder_id: str, folder: str
    ) -> None:
        """Create the backup folder."""
        self.logger.debug("Creating folder %s", folder)
        request_body = DriveItem(
            name=folder,
            folder=Folder(),
            additional_data={
                "@microsoft_graph_conflict_behavior": "fail",
            },
        )
        try:
            await items.by_drive_item_id(base_folder_id).children.post(request_body)
        except APIError as err:
            self.logger.exception("Failed to create folder %s", folder)
            raise AbortFlow(reason="failed_to_create_folder") from err
