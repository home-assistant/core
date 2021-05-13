"""Class representing Sonos favorites."""
from __future__ import annotations

from collections.abc import Iterator
import datetime
import logging

from pysonos.core import SoCo
from pysonos.data_structures import DidlFavorite
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_HOUSEHOLD_UPDATED

_LOGGER = logging.getLogger(__name__)


class SonosFavorites:
    """Storage class for Sonos favorites."""

    def __init__(self, hass: HomeAssistant, soco: SoCo) -> None:
        """Initialize the data."""
        self.hass = hass
        self.soco = soco
        self._favorites: list[DidlFavorite] = []
        self._event_version: str | None = None

    def __iter__(self) -> Iterator:
        """Return an iterator for the known favorites."""
        return iter(self._favorites)

    async def async_delayed_update(self, event: SonosEvent) -> None:
        """Add a delay when triggered by an event.

        Updated favorites are not always immediately available.

        """
        event_id = event.variables["favorites_update_id"]
        if not self._event_version:
            self._event_version = event_id
            return

        if self._event_version == event_id:
            _LOGGER.debug("Favorites haven't changed (event_id: %s)", event_id)
            return

        self._event_version = event_id
        self.hass.helpers.event.async_call_later(5, self.update)

    def update(self, now: datetime.datetime | None = None) -> None:
        """Request new Sonos favorites from a speaker."""
        new_favorites = self.soco.music_library.get_sonos_favorites()

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
        dispatcher_send(
            self.hass, f"{SONOS_HOUSEHOLD_UPDATED}-{self.soco.household_id}"
        )
