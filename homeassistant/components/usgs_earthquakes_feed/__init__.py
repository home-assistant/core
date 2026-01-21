"""The usgs_earthquakes_feed component."""

from __future__ import annotations

from datetime import timedelta
import logging

from aio_geojson_usgs_earthquakes import UsgsEarthquakeHazardsProgramFeedManager
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
    CONF_FEED_TYPE,
    CONF_MINIMUM_MAGNITUDE,
    DEFAULT_MINIMUM_MAGNITUDE,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    VALID_FEED_TYPES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_FEED_TYPE): vol.In(VALID_FEED_TYPES),
                vol.Optional(CONF_LATITUDE): cv.latitude,
                vol.Optional(CONF_LONGITUDE): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
                vol.Optional(
                    CONF_MINIMUM_MAGNITUDE, default=DEFAULT_MINIMUM_MAGNITUDE
                ): cv.positive_float,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

type UsgsEarthquakesFeedConfigEntry = ConfigEntry[UsgsEarthquakesFeedEntityManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the USGS Earthquakes Feed component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    feed_type = conf[CONF_FEED_TYPE]
    radius = conf[CONF_RADIUS]
    minimum_magnitude = conf[CONF_MINIMUM_MAGNITUDE]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_FEED_TYPE: feed_type,
                CONF_RADIUS: radius,
                CONF_MINIMUM_MAGNITUDE: minimum_magnitude,
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: UsgsEarthquakesFeedConfigEntry
) -> bool:
    """Set up the USGS Earthquakes Feed component as config entry."""
    # Create feed entity manager for all platforms.
    manager = UsgsEarthquakesFeedEntityManager(hass, config_entry)
    config_entry.runtime_data = manager
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    await manager.async_init()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UsgsEarthquakesFeedConfigEntry
) -> bool:
    """Unload a USGS Earthquakes Feed component config entry."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class UsgsEarthquakesFeedEntityManager:
    """Feed Entity Manager for USGS Earthquake Hazards Program feed."""

    def __init__(
        self, hass: HomeAssistant, config_entry: UsgsEarthquakesFeedConfigEntry
    ) -> None:
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        self._config_entry = config_entry
        coordinates = (
            config_entry.data[CONF_LATITUDE],
            config_entry.data[CONF_LONGITUDE],
        )
        websession = aiohttp_client.async_get_clientsession(hass)
        self._feed_manager = UsgsEarthquakeHazardsProgramFeedManager(
            websession,
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            config_entry.data[CONF_FEED_TYPE],
            filter_radius=config_entry.data[CONF_RADIUS],
            filter_minimum_magnitude=config_entry.data[CONF_MINIMUM_MAGNITUDE],
        )
        self._config_entry_id = config_entry.entry_id
        self._scan_interval = timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
        self._track_time_remove_callback = None
        self.listeners: list = []

    async def async_init(self) -> None:
        """Schedule initial and regular updates based on configured time interval."""
        await self._hass.config_entries.async_forward_entry_setups(
            self._config_entry, PLATFORMS
        )

        async def update(event_time) -> None:
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
        return f"usgs_earthquakes_feed_new_geolocation_{self._config_entry_id}"

    def get_entry(self, external_id: str):
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
        async_dispatcher_send(
            self._hass, f"usgs_earthquakes_feed_update_{external_id}"
        )

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(
            self._hass, f"usgs_earthquakes_feed_delete_{external_id}"
        )
