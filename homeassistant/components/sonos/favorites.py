"""Class representing Sonos favorites."""
from __future__ import annotations

from collections.abc import Iterator
import logging

from pysonos.core import SoCo
from pysonos.data_structures import DidlFavorite
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

_LOGGER = logging.getLogger(__name__)


class SonosFavorites:
    """Storage class for Sonos favorites."""

    def __init__(self, soco: SoCo) -> None:
        """Initialize the data."""
        self.soco = soco
        self._favorites: list[DidlFavorite] = []
        self._event_version: str | None = None
        self._poll_version: int | None = None

    def __iter__(self) -> Iterator:
        """Return an iterator for the known favorites."""
        return iter(self._favorites)

    def update(self, event: SonosEvent | None = None) -> None:
        """Update favorites with an event or by polling."""
        if event and "favorites_update_id" in event.variables:
            event_id = event.variables["favorites_update_id"]
            if self._event_version == event_id:
                _LOGGER.debug("favorites haven't changed (event_id: %s)", event_id)
                return
            self._event_version = event_id

        new_favorites = self.soco.music_library.get_sonos_favorites()
        if self._poll_version == new_favorites.update_id:
            _LOGGER.debug(
                "Favorites haven't changed (poll_id: %s)", new_favorites.update_id
            )
            return
        self._poll_version = new_favorites.update_id

        self._favorites = []
        for fav in new_favorites:
            try:
                # exclude non-playable favorites with no linked resources
                if fav.reference.resources:
                    self._favorites.append(fav)
            except SoCoException as ex:
                # Skip unknown types
                _LOGGER.error("Unhandled favorite '%s': %s", fav.title, ex)
        _LOGGER.debug(
            "Cached %s favorites for household %s",
            len(self._favorites),
            self.soco.household_id,
        )
