"""Entity manager for generic GeoJSON events."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from aio_geojson_generic_client import GenericFeedManager
from aio_geojson_generic_client.feed_entry import GenericFeedEntry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
)

_LOGGER = logging.getLogger(__name__)


class GeoJsonFeedEntityManager:
    """Feed Entity Manager for GeoJSON feeds."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the GeoJSON Feed Manager."""
        self._hass = hass
        self._config_entry = config_entry
        coordinates: tuple[float, float] = (
            config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        )
        self._url = config_entry.data[CONF_URL]
        radius_in_km = config_entry.data[CONF_RADIUS]
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = GenericFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            self._url,
            filter_radius=radius_in_km,
        )
        self._config_entry_id = config_entry.entry_id
        self._scan_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        self._track_time_remove_callback: Callable[[], None] | None = None
        self.listeners: list[Callable[[], None]] = []
        self.signal_new_entity = f"{DOMAIN}_new_geolocation_{self._config_entry_id}"

    async def async_init(self) -> None:
        """Schedule initial and regular updates based on configured time interval."""

        await self._hass.config_entries.async_forward_entry_setups(
            self._config_entry, PLATFORMS
        )

        async def update(event_time: datetime) -> None:
            """Update."""
            await self.async_update()

        # Trigger updates at regular intervals.
        self._track_time_remove_callback = async_track_time_interval(
            self._hass, update, self._scan_interval
        )

        _LOGGER.debug("Feed entity manager initialized")

    async def async_update(self) -> None:
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity manager updated")

    async def async_stop(self) -> None:
        """Stop this feed entity manager from refreshing."""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []
        if self._track_time_remove_callback:
            self._track_time_remove_callback()
        _LOGGER.debug("Feed entity manager stopped")

    def get_entry(self, external_id: str) -> GenericFeedEntry | None:
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    async def _generate_entity(self, external_id: str) -> None:
        """Generate new entity."""
        async_dispatcher_send(
            self._hass,
            self.signal_new_entity,
            self,
            self._config_entry.unique_id,
            external_id,
        )

    async def _update_entity(self, external_id: str) -> None:
        """Update entity."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))
