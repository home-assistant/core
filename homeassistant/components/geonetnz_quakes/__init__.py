"""The GeoNet NZ Quakes integration."""
import logging
from datetime import timedelta

import voluptuous as vol
from aio_geojson_geonetnz_quakes import GeonetnzQuakesFeedManager

from homeassistant.components.geonetnz_quakes.geo_location import GeonetnzQuakesEvent
from .const import (
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    SIGNAL_STATUS,
    DEFAULT_FILTER_TIME_INTERVAL,
)

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv, aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import (
    CONF_MINIMUM_MAGNITUDE,
    CONF_MMI,
    DEFAULT_MINIMUM_MAGNITUDE,
    DEFAULT_MMI,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    COMPONENTS,
    FEED,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_LATITUDE): cv.latitude,
                vol.Optional(CONF_LONGITUDE): cv.longitude,
                vol.Optional(CONF_MMI, default=DEFAULT_MMI): vol.All(
                    vol.Coerce(int), vol.Range(min=-1, max=8)
                ),
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
                vol.Optional(
                    CONF_MINIMUM_MAGNITUDE, default=DEFAULT_MINIMUM_MAGNITUDE
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the GeoNet NZ Quakes component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    mmi = conf[CONF_MMI]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    identifier = f"{latitude}, {longitude}"
    if identifier in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS],
                CONF_MINIMUM_MAGNITUDE: conf[CONF_MINIMUM_MAGNITUDE],
                CONF_MMI: mmi,
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the GeoNet NZ Quakes component as config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if FEED not in hass.data[DOMAIN]:
        hass.data[DOMAIN][FEED] = {}

    for domain in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an GeoNet NZ Quakes component config entry."""
    manager = hass.data[DOMAIN][FEED].pop(config_entry.entry_id)
    await manager.async_stop()

    for domain in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(config_entry, domain)
        )

    return True


class GeonetnzQuakesFeedEntityManager:
    """Feed Entity Manager for GeoNet NZ Quakes feed."""

    def __init__(
        self,
        hass,
        async_add_entities,
        config_entry_id,
        scan_interval,
        latitude,
        longitude,
        mmi,
        radius_in_km,
        unit_system,
        minimum_magnitude,
    ):
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        coordinates = (latitude, longitude)
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = GeonetnzQuakesFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            mmi=mmi,
            filter_radius=radius_in_km,
            filter_minimum_magnitude=minimum_magnitude,
            filter_time=DEFAULT_FILTER_TIME_INTERVAL,
            status_callback=self._status_update,
        )
        self._async_add_entities = async_add_entities
        self._config_entry_id = config_entry_id
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unit_system = unit_system
        self._track_time_remove_callback = None
        self._status_info = None

    async def async_init(self):
        """Schedule regular updates based on configured time interval."""

        async def update(event_time):
            """Update."""
            await self.async_update()

        await self.async_update()
        self._track_time_remove_callback = async_track_time_interval(
            self._hass, update, self._scan_interval
        )
        _LOGGER.debug("Feed entity manager initialized")

    async def async_update(self):
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity manager updated")

    async def async_stop(self):
        """Stop this feed entity manager from refreshing."""
        if self._track_time_remove_callback:
            self._track_time_remove_callback()
        _LOGGER.debug("Feed entity manager stopped")

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    def status_info(self):
        """Return latest status update info received."""
        return self._status_info

    async def _generate_entity(self, external_id):
        """Generate new entity."""
        new_entity = GeonetnzQuakesEvent(self, external_id, self._unit_system)
        # Add new entities to HA.
        self._async_add_entities([new_entity], True)

    async def _update_entity(self, external_id):
        """Update entity."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id):
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))

    async def _status_update(self, status_info):
        """Propagate status update."""
        _LOGGER.debug("Status update received: %s", status_info)
        self._status_info = status_info
        async_dispatcher_send(self._hass, SIGNAL_STATUS.format(self._config_entry_id))
