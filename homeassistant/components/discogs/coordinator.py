"""DataUpdateCoordinator for the Discogs integration."""

from dataclasses import dataclass
from datetime import timedelta
import random
from typing import override

import discogs_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type DiscogsConfigEntry = ConfigEntry[DiscogsDataUpdateCoordinator]


@dataclass
class DiscogsData:
    """Data holder for Discogs data."""

    username: str
    collection_count: int
    wantlist_count: int
    random_record: str | None
    random_record_attrs: dict | None


class DiscogsDataUpdateCoordinator(DataUpdateCoordinator[DiscogsData]):
    """A Discogs Data Update Coordinator."""

    config_entry: DiscogsConfigEntry
    _client: discogs_client.Client

    def __init__(self, hass: HomeAssistant, config_entry: DiscogsConfigEntry) -> None:
        """Initialize the Discogs data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=10),
        )
        self._client = discogs_client.Client(
            SERVER_SOFTWARE, user_token=config_entry.data[CONF_TOKEN]
        )

    @override
    async def _async_update_data(self) -> DiscogsData:
        """Fetch data from Discogs."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except discogs_client.exceptions.HTTPError as err:
            raise UpdateFailed(f"Error communicating with Discogs: {err}") from err

    def _fetch_data(self) -> DiscogsData:
        """Fetch data from Discogs (runs in executor)."""
        identity = self._client.identity()
        username = identity.name
        collection_count = identity.num_collection
        wantlist_count = identity.num_wantlist

        random_record = None
        random_record_attrs = None
        folders = identity.collection_folders
        if folders and folders[0].count > 0:
            collection = folders[0]
            random_index = random.randrange(collection.count)
            release = collection.releases[random_index].release
            random_record = (
                f"{release.data['artists'][0]['name']} - {release.data['title']}"
            )
            random_record_attrs = {
                "cat_no": release.data["labels"][0]["catno"],
                "cover_image": release.data["cover_image"],
                "format": (
                    f"{release.data['formats'][0]['name']}"
                    f" ({release.data['formats'][0]['descriptions'][0]})"
                ),
                "label": release.data["labels"][0]["name"],
                "released": release.data["year"],
            }

        return DiscogsData(
            username=username,
            collection_count=collection_count,
            wantlist_count=wantlist_count,
            random_record=random_record,
            random_record_attrs=random_record_attrs,
        )
