"""The Global Disaster Alert and Coordination System (GDACS) integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from aio_georss_client.status_update import StatusUpdate
from aio_georss_gdacs import GdacsFeedManager
from aio_georss_gdacs.feed_entry import FeedEntry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (  # noqa: F401
    CONF_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEED,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the GDACS component as config entry."""
    hass.data.setdefault(DOMAIN, {})
    feeds = hass.data[DOMAIN].setdefault(FEED, {})

    radius = config_entry.data[CONF_RADIUS]
    if hass.config.units is US_CUSTOMARY_SYSTEM:
        radius = DistanceConverter.convert(
            radius, UnitOfLength.MILES, UnitOfLength.KILOMETERS
        )
    # Create feed entity manager for all platforms.
    manager = GdacsFeedEntityManager(hass, config_entry, radius)
    feeds[config_entry.entry_id] = manager
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    await manager.async_init()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an GDACS component config entry."""
    manager: GdacsFeedEntityManager = hass.data[DOMAIN][FEED].pop(entry.entry_id)
    await manager.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class GdacsFeedEntityManager:
    """Feed Entity Manager for GDACS feed."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, radius_in_km: float
    ) -> None:
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        self._config_entry = config_entry
        coordinates = (
            config_entry.data[CONF_LATITUDE],
            config_entry.data[CONF_LONGITUDE],
        )
        categories = config_entry.data[CONF_CATEGORIES]
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = GdacsFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            filter_radius=radius_in_km,
            filter_categories=categories,
            status_async_callback=self._status_update,
        )
        self._config_entry_id = config_entry.entry_id
        self._scan_interval = timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
        self._track_time_remove_callback: Callable[[], None] | None = None
        self._status_info: StatusUpdate | None = None
        self.listeners: list[Callable[[], None]] = []

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

    @callback
    def async_event_new_entity(self) -> str:
        """Return manager specific event to signal new entity."""
        return f"gdacs_new_geolocation_{self._config_entry_id}"

    def get_entry(self, external_id: str) -> FeedEntry | None:
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    def status_info(self) -> StatusUpdate | None:
        """Return latest status update info received."""
        return self._status_info

    async def _generate_entity(self, external_id: str) -> None:
        """Generate new entity."""
        async_dispatcher_send(
            self._hass,
            self.async_event_new_entity(),
            self,
            self._config_entry.unique_id,
            external_id,
        )

    async def _update_entity(self, external_id: str) -> None:
        """Update entity."""
        async_dispatcher_send(self._hass, f"gdacs_update_{external_id}")

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(self._hass, f"gdacs_delete_{external_id}")

    async def _status_update(self, status_info: StatusUpdate) -> None:
        """Propagate status update."""
        _LOGGER.debug("Status update received: %s", status_info)
        self._status_info = status_info
        async_dispatcher_send(self._hass, f"gdacs_status_{self._config_entry_id}")
