"""Coordinator for fetching data from Google Photos API.

This coordinator fetches the list of Google Photos albums that were created by
Home Assistant, which for large libraries may take some time. The list of album
ids and titles is cached and this provides a method to refresh urls since they
are short lived.
"""

import asyncio
import datetime
import logging
from typing import Final

from google_photos_library_api.api import GooglePhotosLibraryApi
from google_photos_library_api.exceptions import GooglePhotosApiError
from google_photos_library_api.model import Album

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = datetime.timedelta(hours=24)
ALBUM_PAGE_SIZE = 50


class GooglePhotosUpdateCoordinator(DataUpdateCoordinator[dict[str, str] | None]):
    """Coordinator for fetching Google Photos albums.

    The `data` object is a dict from Album ID to Album title.
    """

    def __init__(self, hass: HomeAssistant, client: GooglePhotosLibraryApi) -> None:
        """Initialize TaskUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Google Photos",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch albums from API endpoint."""
        albums: dict[str, str] = {}
        try:
            async for album_result in await self.client.list_albums(
                page_size=ALBUM_PAGE_SIZE
            ):
                for album in album_result.albums:
                    albums[album.id] = album.title
        except GooglePhotosApiError as err:
            _LOGGER.debug("Error listing albums: %s", err)
            raise UpdateFailed(f"Error listing albums: {err}") from err
        return albums

    async def list_albums(self) -> list[Album]:
        """Return Albums with refreshed URLs based on the cached list of album ids."""
        if self.data is None:
            key = "albums_not_loaded" if self.last_update_success else "albums_failed"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
            )
        return await asyncio.gather(
            *(self.client.get_album(album_id) for album_id in self.data)
        )
