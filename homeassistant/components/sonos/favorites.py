"""Class representing Sonos favorites."""

from __future__ import annotations

from collections.abc import Iterator
import logging
import re
from typing import TYPE_CHECKING, Any

from soco import SoCo
from soco.data_structures import DidlFavorite
from soco.events_base import Event as SonosEvent
from soco.exceptions import SoCoException

from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

from .const import SONOS_CREATE_FAVORITES_SENSOR, SONOS_FAVORITES_UPDATED
from .helpers import soco_error
from .household_coordinator import SonosHouseholdCoordinator

if TYPE_CHECKING:
    from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


class SonosFavorites(SonosHouseholdCoordinator):
    """Coordinator class for Sonos favorites."""

    def __init__(self, *args: Any) -> None:
        """Initialize the data."""
        super().__init__(*args)
        self._favorites: list[DidlFavorite] = []
        self.last_polled_ids: dict[str, int] = {}

    def __iter__(self) -> Iterator[DidlFavorite]:
        """Return an iterator for the known favorites."""
        favorites = self._favorites.copy()
        return iter(favorites)

    def setup(self, soco: SoCo) -> None:
        """Override to send a signal on base class setup completion."""
        super().setup(soco)
        dispatcher_send(self.hass, SONOS_CREATE_FAVORITES_SENSOR, self)

    @property
    def count(self) -> int:
        """Return the number of favorites."""
        return len(self._favorites)

    def lookup_by_item_id(self, item_id: str) -> DidlFavorite | None:
        """Return the favorite object with the provided item_id."""
        return next((fav for fav in self._favorites if fav.item_id == item_id), None)

    async def async_update_entities(
        self, soco: SoCo, update_id: int | None = None
    ) -> None:
        """Update the cache and update entities."""
        updated = await self.hass.async_add_executor_job(
            self.update_cache, soco, update_id
        )
        if not updated:
            return

        async_dispatcher_send(
            self.hass, f"{SONOS_FAVORITES_UPDATED}-{self.household_id}"
        )

    async def async_process_event(
        self, event: SonosEvent, speaker: SonosSpeaker
    ) -> None:
        """Process the event payload in an async lock and update entities."""
        event_id = event.variables["favorites_update_id"]
        container_ids = event.variables["container_update_i_ds"]
        if not (match := re.search(r"FV:2,(\d+)", container_ids)):
            return

        container_id = int(match.groups()[0])
        event_id = int(event_id.split(",")[-1])

        async with self.cache_update_lock:
            last_poll_id = self.last_polled_ids.get(speaker.uid)
            if (
                self.last_processed_event_id
                and event_id <= self.last_processed_event_id
            ):
                # Skip updates if this event_id has already been seen
                if not last_poll_id:
                    self.last_polled_ids[speaker.uid] = container_id
                return

            if last_poll_id and container_id <= last_poll_id:
                return

            speaker.event_stats.process(event)
            _LOGGER.debug(
                "New favorites event %s from %s (was %s)",
                event_id,
                speaker.soco,
                self.last_processed_event_id,
            )
            self.last_processed_event_id = event_id
            await self.async_update_entities(speaker.soco, container_id)

    @soco_error()
    def update_cache(self, soco: SoCo, update_id: int | None = None) -> bool:
        """Update cache of known favorites and return if cache has changed."""
        new_favorites = soco.music_library.get_sonos_favorites(full_album_art_uri=True)
        new_playlists = soco.music_library.get_music_library_information(
            "sonos_playlists", full_album_art_uri=True
        )

        # Polled update_id values do not match event_id values
        # Each speaker can return a different polled update_id
        last_poll_id = self.last_polled_ids.get(soco.uid)
        if last_poll_id and new_favorites.update_id <= last_poll_id:
            # Skip updates already processed
            return False
        self.last_polled_ids[soco.uid] = new_favorites.update_id

        _LOGGER.debug(
            "Processing favorites update_id %s for %s (was: %s)",
            new_favorites.update_id,
            soco,
            last_poll_id,
        )

        self._favorites = []
        for fav in new_favorites:
            try:
                # exclude non-playable favorites with no linked resources
                if fav.reference.resources:
                    self._favorites.append(fav)
            except SoCoException as ex:
                # Skip unknown types
                _LOGGER.error("Unhandled favorite '%s': %s", fav.title, ex)
        for playlist in new_playlists:
            playlist_reference = DidlFavorite(
                title=playlist.title,
                parent_id=playlist.parent_id,
                item_id=playlist.item_id,
                resources=playlist.resources,
                desc=playlist.desc,
            )
            playlist_reference.reference = playlist
            self._favorites.append(playlist_reference)

        _LOGGER.debug(
            "Cached %s favorites for household %s using %s",
            len(self._favorites),
            self.household_id,
            soco,
        )
        return True
