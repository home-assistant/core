"""API for Google Photos bound to Home Assistant OAuth."""

from abc import ABC, abstractmethod
from functools import partial
import logging
from typing import Any, cast

from aiohttp.client_exceptions import ClientError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .exceptions import GooglePhotosApiError

_LOGGER = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20

# Only included necessary fields to limit response sizes
GET_MEDIA_ITEM_FIELDS = (
    "id,baseUrl,mimeType,filename,mediaMetadata(width,height,photo,video)"
)
LIST_MEDIA_ITEM_FIELDS = f"nextPageToken,mediaItems({GET_MEDIA_ITEM_FIELDS})"
UPLOAD_API = "https://photoslibrary.googleapis.com/v1/uploads"
LIST_ALBUMS_FIELDS = (
    "nextPageToken,albums(id,title,coverPhotoBaseUrl,coverPhotoMediaItemId)"
)


class AuthBase(ABC):
    """Base class for Google Photos authentication library.

    Provides an asyncio interface around the blocking client library.
    """

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize Google Photos auth."""
        self._hass = hass

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def get_user_info(self) -> dict[str, Any]:
        """Get the user profile info."""
        service = await self._get_profile_service()
        cmd: HttpRequest = service.userinfo().get()
        return await self._execute(cmd)

    async def get_media_item(self, media_item_id: str) -> dict[str, Any]:
        """Get all MediaItem resources."""
        service = await self._get_photos_service()
        cmd: HttpRequest = service.mediaItems().get(
            mediaItemId=media_item_id, fields=GET_MEDIA_ITEM_FIELDS
        )
        return await self._execute(cmd)

    async def list_media_items(
        self,
        page_size: int | None = None,
        page_token: str | None = None,
        album_id: str | None = None,
        favorites: bool = False,
    ) -> dict[str, Any]:
        """Get all MediaItem resources."""
        service = await self._get_photos_service()
        args: dict[str, Any] = {
            "pageSize": (page_size or DEFAULT_PAGE_SIZE),
            "pageToken": page_token,
        }
        cmd: HttpRequest
        if album_id is not None or favorites:
            if album_id is not None:
                args["albumId"] = album_id
            if favorites:
                args["filters"] = {"featureFilter": {"includedFeatures": "FAVORITES"}}
            cmd = service.mediaItems().search(body=args, fields=LIST_MEDIA_ITEM_FIELDS)
        else:
            cmd = service.mediaItems().list(**args, fields=LIST_MEDIA_ITEM_FIELDS)
        return await self._execute(cmd)

    async def list_albums(
        self, page_size: int | None = None, page_token: str | None = None
    ) -> dict[str, Any]:
        """Get all Album resources."""
        service = await self._get_photos_service()
        cmd: HttpRequest = service.albums().list(
            pageSize=(page_size or DEFAULT_PAGE_SIZE),
            pageToken=page_token,
            fields=LIST_ALBUMS_FIELDS,
        )
        return await self._execute(cmd)

    async def upload_content(self, content: bytes, mime_type: str) -> str:
        """Upload media content to the API and return an upload token."""
        token = await self.async_get_access_token()
        session = aiohttp_client.async_get_clientsession(self._hass)
        try:
            result = await session.post(
                UPLOAD_API, headers=_upload_headers(token, mime_type), data=content
            )
            result.raise_for_status()
            return await result.text()
        except ClientError as err:
            raise GooglePhotosApiError(f"Failed to upload content: {err}") from err

    async def create_media_items(self, upload_tokens: list[str]) -> list[str]:
        """Create a batch of media items and return the ids."""
        service = await self._get_photos_service()
        cmd: HttpRequest = service.mediaItems().batchCreate(
            body={
                "newMediaItems": [
                    {
                        "simpleMediaItem": {
                            "uploadToken": upload_token,
                        }
                        for upload_token in upload_tokens
                    }
                ]
            }
        )
        result = await self._execute(cmd)
        return [
            media_item["mediaItem"]["id"]
            for media_item in result["newMediaItemResults"]
        ]

    async def _get_photos_service(self) -> Resource:
        """Get current photos library API resource."""
        token = await self.async_get_access_token()
        return await self._hass.async_add_executor_job(
            partial(
                build,
                "photoslibrary",
                "v1",
                credentials=Credentials(token=token),  # type: ignore[no-untyped-call]
                static_discovery=False,
            )
        )

    async def _get_profile_service(self) -> Resource:
        """Get current profile service API resource."""
        token = await self.async_get_access_token()
        return await self._hass.async_add_executor_job(
            partial(build, "oauth2", "v2", credentials=Credentials(token=token))  # type: ignore[no-untyped-call]
        )

    async def _execute(self, request: HttpRequest) -> dict[str, Any]:
        try:
            result = await self._hass.async_add_executor_job(request.execute)
        except HttpError as err:
            raise GooglePhotosApiError(
                f"Google Photos API responded with error ({err.status_code}): {err.reason}"
            ) from err
        if not isinstance(result, dict):
            raise GooglePhotosApiError(
                f"Google Photos API replied with unexpected response: {result}"
            )
        if error := result.get("error"):
            message = error.get("message", "Unknown Error")
            raise GooglePhotosApiError(f"Google Photos API response: {message}")
        return cast(dict[str, Any], result)


class AsyncConfigEntryAuth(AuthBase):
    """Provide Google Photos authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize AsyncConfigEntryAuth."""
        super().__init__(hass)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token[CONF_ACCESS_TOKEN])


class AsyncConfigFlowAuth(AuthBase):
    """An API client used during the config flow with a fixed token."""

    def __init__(
        self,
        hass: HomeAssistant,
        token: str,
    ) -> None:
        """Initialize ConfigFlowAuth."""
        super().__init__(hass)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._token


def _upload_headers(token: str, mime_type: str) -> dict[str, Any]:
    """Create the upload headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "X-Goog-Upload-Content-Type": mime_type,
        "X-Goog-Upload-Protocol": "raw",
    }
