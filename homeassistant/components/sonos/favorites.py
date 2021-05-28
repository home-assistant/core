"""Class representing Sonos favorites."""
from __future__ import annotations

from collections.abc import Iterator
import datetime
import logging
from typing import Callable

from pysonos.data_structures import DidlFavorite
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DATA_SONOS, SONOS_HOUSEHOLD_UPDATED

_LOGGER = logging.getLogger(__name__)


class SonosFavorites:
    """Storage class for Sonos favorites."""

    def __init__(self, hass: HomeAssistant, household_id: str) -> None:
        """Initialize the data."""
        self.hass = hass
        self.household_id = household_id
        self._favorites: list[DidlFavorite] = []
        self._event_version: str | None = None
        self._next_update: Callable | None = None

    def __iter__(self) -> Iterator:
        """Return an iterator for the known favorites."""
        favorites = self._favorites.copy()
        return iter(favorites)

    @callback
    def async_delayed_update(self, event: SonosEvent) -> None:
        """Add a delay when triggered by an event.

        Updated favorites are not always immediately available.

        """
        if not (event_id := event.variables.get("favorites_update_id")):
            return

        if not self._event_version:
            self._event_version = event_id
            return

        if self._event_version == event_id:
            _LOGGER.debug("Favorites haven't changed (event_id: %s)", event_id)
            return

        self._event_version = event_id

        if self._next_update:
            self._next_update()

        self._next_update = self.hass.helpers.event.async_call_later(3, self.update)

    def update(self, now: datetime.datetime | None = None) -> None:
        """Request new Sonos favorites from a speaker."""
        new_favorites = None
        discovered = self.hass.data[DATA_SONOS].discovered

        for uid, speaker in discovered.items():
            try:
                new_favorites = speaker.soco.music_library.get_sonos_favorites()
            except SoCoException as err:
                _LOGGER.warning(
                    "Error requesting favorites from %s: %s", speaker.soco, err
                )
            else:
                # Prefer this SoCo instance next update
                discovered.move_to_end(uid, last=False)
                break

        if new_favorites is None:
            _LOGGER.error("Could not reach any speakers to update favorites")
            return

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
            self.household_id,
        )
        dispatcher_send(self.hass, f"{SONOS_HOUSEHOLD_UPDATED}-{self.household_id}")
