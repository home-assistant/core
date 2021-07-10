"""Class representing Sonos favorites."""
from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Any

from pysonos import SoCo
from pysonos.data_structures import DidlFavorite
from pysonos.exceptions import SoCoException

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import SONOS_FAVORITES_UPDATED
from .household_coordinator import SonosHouseholdCoordinator

_LOGGER = logging.getLogger(__name__)


class SonosFavorites(SonosHouseholdCoordinator):
    """Coordinator class for Sonos favorites."""

    def __init__(self, *args: Any) -> None:
        """Initialize the data."""
        super().__init__(*args)
        self._favorites: list[DidlFavorite] = []

    def __iter__(self) -> Iterator:
        """Return an iterator for the known favorites."""
        favorites = self._favorites.copy()
        return iter(favorites)

    async def async_update_entities(self, soco: SoCo) -> bool:
        """Update the cache and update entities."""
        try:
            await self.hass.async_add_executor_job(self.update_cache, soco)
        except (OSError, SoCoException) as err:
            _LOGGER.warning("Error requesting favorites from %s: %s", soco, err)
            return False

        async_dispatcher_send(
            self.hass, f"{SONOS_FAVORITES_UPDATED}-{self.household_id}"
        )
        return True

    def update_cache(self, soco: SoCo) -> None:
        """Request new Sonos favorites from a speaker."""
        new_favorites = soco.music_library.get_sonos_favorites()
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
