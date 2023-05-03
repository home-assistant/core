"""Entity manager for generic GeoJSON events."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from aio_geojson_generic_client import GenericFeedManager
from aio_geojson_generic_client.feed_entry import GenericFeedEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SIGNAL_DELETE_ENTITY, SIGNAL_UPDATE_ENTITY

_LOGGER = logging.getLogger(__name__)


class GeoJsonFeedEntityManager:
    """Feed Entity Manager for GeoJSON feeds."""

    def __init__(
        self,
        hass: HomeAssistant,
        scan_interval: timedelta,
        coordinates: tuple[float, float],
        url: str,
        radius_in_km: float,
    ) -> None:
        """Initialize the GeoJSON Feed Manager."""

        self._hass = hass
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = GenericFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            url,
            filter_radius=radius_in_km,
        )
        self._scan_interval = scan_interval
        self.signal_new_entity = (
            f"{DOMAIN}_new_geolocation_{coordinates}-{url}-{radius_in_km}"
        )

    async def async_init(self) -> None:
        """Schedule initial and regular updates based on configured time interval."""

        async def update(event_time: datetime) -> None:
            """Update."""
            await self.async_update()

        # Trigger updates at regular intervals.
        async_track_time_interval(self._hass, update, self._scan_interval)
        _LOGGER.debug("Feed entity manager initialized")

    async def async_update(self) -> None:
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity manager updated")

    def get_entry(self, external_id: str) -> GenericFeedEntry | None:
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    async def _generate_entity(self, external_id: str) -> None:
        """Generate new entity."""
        async_dispatcher_send(
            self._hass,
            self.signal_new_entity,
            self,
            external_id,
        )

    async def _update_entity(self, external_id: str) -> None:
        """Update entity."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))
