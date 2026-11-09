"""Coordinator for the Seafile integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from aioseafile import (
    Library,
    Seafile,
    SeafileAuthenticationError,
    SeafileError,
    SeafilePermissionError,
    SeafileTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LIBRARY_ID, DOMAIN, LOGGER, SUBENTRY_TYPE_LIBRARY
from .utils import handle_seafile_errors

type SeafileConfigEntry = ConfigEntry[SeafileDataUpdateCoordinator]

UPDATE_INTERVAL = timedelta(minutes=5)


@dataclass
class SeafileData:
    """Data of the libraries of a Seafile account."""

    libraries: dict[str, Library]
    file_counts: dict[str, int]
    history_limits: dict[str, int]


class SeafileDataUpdateCoordinator(DataUpdateCoordinator[SeafileData]):
    """Fetch the libraries of a Seafile account."""

    config_entry: SeafileConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SeafileConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = Seafile(
            config_entry.data[CONF_URL],
            config_entry.data[CONF_TOKEN],
            session=async_get_clientsession(
                hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL]
            ),
        )

    @override
    async def _async_update_data(self) -> SeafileData:
        """Fetch the libraries added as subentries."""
        library_ids = [
            subentry.data[CONF_LIBRARY_ID]
            for subentry in self.config_entry.get_subentries_of_type(
                SUBENTRY_TYPE_LIBRARY
            )
        ]
        try:
            libraries = {
                library.id: library for library in await self.client.get_libraries()
            }
            # Only the details of a single library include its file count.
            details = await asyncio.gather(
                *(
                    self.client.get_library(library_id)
                    for library_id in library_ids
                    if library_id in libraries
                )
            )
            # Only the owner, or a user the library is shared with as admin,
            # can read the history setting of a library.
            owned_library_ids = [
                library_id
                for library_id in library_ids
                if library_id in libraries
                and (
                    libraries[library_id].type == "repo"
                    or libraries[library_id].permission == "admin"
                )
            ]
            history_limits = await asyncio.gather(
                *(
                    self._async_get_history_limit(library_id)
                    for library_id in owned_library_ids
                )
            )
        except SeafileAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except SeafileTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="timeout_connect"
            ) from err
        except SeafileError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        else:
            return SeafileData(
                libraries=libraries,
                file_counts={detail.id: detail.file_count for detail in details},
                history_limits={
                    library_id: keep_days
                    for library_id, keep_days in zip(
                        owned_library_ids, history_limits, strict=True
                    )
                    if keep_days is not None
                },
            )

    async def async_set_history_limit(self, library_id: str, keep_days: int) -> None:
        """Change the days of history a library keeps and update the entities."""
        async with handle_seafile_errors():
            keep_days = await self.client.set_library_history_limit(
                library_id, keep_days
            )
        self.data.history_limits[library_id] = keep_days
        self.async_update_listeners()

    async def _async_get_history_limit(self, library_id: str) -> int | None:
        """Return the days of history a library keeps, if the server allows it."""
        try:
            return await self.client.get_library_history_limit(library_id)
        except SeafilePermissionError:
            # Virtual libraries have no history setting.
            return None
