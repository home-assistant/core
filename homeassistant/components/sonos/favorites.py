"""Class representing Sonos favorites."""
from __future__ import annotations

from collections.abc import Iterator
import logging

from pysonos import SoCo
from pysonos.data_structures import DidlFavorite
from pysonos.exceptions import SoCoException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import SONOS_FAVORITES_UPDATED

_LOGGER = logging.getLogger(__name__)


class SonosFavorites:
    """Storage class for Sonos favorites."""

    def __init__(self, hass: HomeAssistant, household_id: str) -> None:
        """Initialize the data."""
        self.hass = hass
        self.household_id = household_id
        self._favorites: list[DidlFavorite] = []
        self._event_version: str | None = None

    def __iter__(self) -> Iterator:
        """Return an iterator for the known favorites."""
        favorites = self._favorites.copy()
        return iter(favorites)

    @callback
    def async_update(self, event_id: str, soco: SoCo) -> None:
        """Update Sonos favorites using the provided SoCo instance."""
        if not self._event_version:
            self._event_version = event_id
            return

        if self._event_version == event_id:
            return

        self._event_version = event_id
        self.hass.async_add_executor_job(self.update, soco)

    def update(self, soco: SoCo) -> None:
        """Request new Sonos favorites from a speaker."""
        try:
            new_favorites = soco.music_library.get_sonos_favorites()
        except (OSError, SoCoException) as err:
            _LOGGER.warning("Error requesting favorites from %s: %s", soco, err)
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
        dispatcher_send(self.hass, f"{SONOS_FAVORITES_UPDATED}-{self.household_id}")
