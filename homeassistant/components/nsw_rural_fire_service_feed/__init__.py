"""The NSW Rural Fire Service Feeds integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from aio_geojson_nsw_rfs_incidents import NswRuralFireServiceIncidentsFeedManager
from aio_geojson_nsw_rfs_incidents.feed_entry import (
    NswRuralFireServiceIncidentsFeedEntry,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CATEGORIES,
    DEFAULT_RADIUS_IN_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEED,
    PLATFORMS,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    VALID_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(
                    float
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(CONF_CATEGORIES, default=[]): vol.All(
                    cv.ensure_list, [vol.In(VALID_CATEGORIES)]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NSW Rural Fire Service Feeds integration."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    scan_interval = conf[CONF_SCAN_INTERVAL]
    categories = conf[CONF_CATEGORIES]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS],
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_CATEGORIES: categories,
            },
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the NSW Rural Fire Service Feeds integration as config entry."""
    hass.data.setdefault(DOMAIN, {})
    feeds = hass.data[DOMAIN].setdefault(FEED, {})

    # Create feed entity manager for all platforms.
    manager = NswRuralFireServiceFeedEntityManager(hass, config_entry)
    feeds[config_entry.entry_id] = manager
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    await manager.async_init()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the NSW Rural Fire Service Feeds integration config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][FEED].pop(entry.entry_id)
    return unload_ok


class NswRuralFireServiceFeedEntityManager:
    """Feed Entity Manager for NSW Rural Fire Service GeoJSON feed."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        self._config_entry = config_entry
        coordinates: tuple[float, float] = (
            config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        )
        radius_in_km = config_entry.data[CONF_RADIUS]
        categories = config_entry.data[CONF_CATEGORIES]
        scan_interval: timedelta = timedelta(
            seconds=config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = NswRuralFireServiceIncidentsFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            filter_radius=radius_in_km,
            filter_categories=categories,
        )
        self._config_entry_id = config_entry.entry_id
        self._scan_interval = scan_interval
        self._track_time_remove_callback: Callable[[], None] | None = None
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
    def async_event_new_entity(self):
        """Return manager specific event to signal new entity."""
        return f"nsw_rural_fire_service_feed_new_geolocation_{self._config_entry_id}"

    def get_entry(
        self, external_id: str
    ) -> NswRuralFireServiceIncidentsFeedEntry | None:
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

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
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))
