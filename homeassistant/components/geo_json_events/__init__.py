"""The GeoJSON events component."""
from datetime import timedelta
import logging

from aio_geojson_generic_client import GenericFeedManager

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_URL,
    LENGTH_MILES,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

from ...config_entries import SOURCE_IMPORT, ConfigEntry
from ...helpers.dispatcher import async_dispatcher_send
from ...helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
from ...helpers.update_coordinator import DataUpdateCoordinator
from ...util.unit_system import METRIC_SYSTEM
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, FEED, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GeoJSON events component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS],
                CONF_URL: conf[CONF_URL],
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the GeoJSON events component as config entry."""
    hass.data.setdefault(DOMAIN, {})
    feeds = hass.data[DOMAIN].setdefault(FEED, {})
    radius = config_entry.data[CONF_RADIUS]
    if hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
        radius = METRIC_SYSTEM.length(radius, LENGTH_MILES)
    # Create feed entity coordinator for all platforms.
    coordinator = GeoJsonEventsFeedEntityCoordinator(hass, config_entry, radius)
    feeds[config_entry.entry_id] = coordinator
    _LOGGER.debug("Feed entity coordinator added for %s", config_entry.entry_id)
    # Remove orphaned geo_location entities.
    entity_registry = await async_get_registry(hass)
    orphaned_entries = async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if orphaned_entries is not None:
        for entry in orphaned_entries:
            if entry.domain == Platform.GEO_LOCATION:
                _LOGGER.debug("Removing entry %s", entry.entity_id)
                entity_registry.async_remove(entry.entity_id)
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an GeoJSON events component config entry."""
    coordinator = hass.data[DOMAIN][FEED].pop(entry.entry_id)
    await coordinator.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class GeoJsonEventsFeedEntityCoordinator(DataUpdateCoordinator):
    """Feed Entity Coordinator for GeoJSON events feed."""

    def __init__(self, hass, config_entry, radius_in_km):
        """Initialize the Feed Entity Coordinator."""
        self.config_entry: ConfigEntry = config_entry
        coordinates = (
            config_entry.data[CONF_LATITUDE],
            config_entry.data[CONF_LONGITUDE],
        )
        websession = aiohttp_client.async_get_clientsession(hass)
        self._url = config_entry.data[CONF_URL]
        self._feed_manager = GenericFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            self._url,
            filter_radius=radius_in_km,
            status_callback=self._status_update,
        )
        self._config_entry_id = config_entry.entry_id
        self._status_info = None
        self.listeners = []
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self._url}",
            update_method=self.async_update,
            update_interval=timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]),
        )

    @property
    def url(self) -> str:
        """Return this instance's url."""
        return self._url

    async def async_update(self):
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity coordinator updated")
        return self._feed_manager.feed_entries

    async def async_stop(self):
        """Stop this feed entity coordinator from refreshing."""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []
        _LOGGER.debug("Feed entity coordinator stopped")

    @callback
    def async_event_new_entity(self):
        """Return coordinator specific event to signal new entity."""
        return f"{DOMAIN}_new_geolocation_{self._config_entry_id}"

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    def entry_available(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id) is not None

    def status_info(self):
        """Return latest status update info received."""
        return self._status_info

    async def _generate_entity(self, external_id: str):
        """Generate new entity."""
        _LOGGER.debug("New entry received for: %s", external_id)
        async_dispatcher_send(
            self.hass,
            self.async_event_new_entity(),
            self,
            self.config_entry.unique_id,
            external_id,
        )

    async def _update_entity(self, external_id: str):
        """Ignore update call; this is handled by the coordinator."""

    async def _remove_entity(self, external_id: str):
        """Remove entity."""
        _LOGGER.debug("Remove received for: %s", external_id)
        async_dispatcher_send(self.hass, f"{DOMAIN}_delete_{external_id}")

    async def _status_update(self, status_info):
        """Store status update."""
        _LOGGER.debug("Status update received: %s", status_info)
        self._status_info = status_info
