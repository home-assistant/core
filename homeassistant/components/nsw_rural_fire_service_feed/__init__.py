"""The nsw_rural_fire_service_feed component."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from aio_geojson_nsw_rfs_incidents import NswRuralFireServiceIncidentsFeedManager
from aio_geojson_nsw_rfs_incidents.feed_entry import (
    NswRuralFireServiceIncidentsFeedEntry,
)
import voluptuous as vol

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CATEGORIES,
    DEFAULT_RADIUS_IN_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    VALID_CATEGORIES,
)
from .geo_location import NswRuralFireServiceLocationEvent

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


class NswRuralFireServiceFeedEntityManager:
    """Feed Entity Manager for NSW Rural Fire Service GeoJSON feed."""

    def __init__(
        self,
        hass: HomeAssistant,
        async_add_entities: AddEntitiesCallback,
        scan_interval: timedelta,
        coordinates: tuple[float, float],
        radius_in_km: float,
        categories: list[str],
    ) -> None:
        """Initialize the Feed Entity Manager."""
        self._hass = hass
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
        self._async_add_entities = async_add_entities
        self._scan_interval = scan_interval
        self._track_time_remove_callback: Callable[[], None] | None = None

    async def async_init(self) -> None:
        """Schedule initial and regular updates based on configured time interval."""

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
        if self._track_time_remove_callback:
            self._track_time_remove_callback()
        _LOGGER.debug("Feed entity manager stopped")

    def get_entry(
        self, external_id: str
    ) -> NswRuralFireServiceIncidentsFeedEntry | None:
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    async def _generate_entity(self, external_id: str) -> None:
        """Generate new entity."""
        new_entity = NswRuralFireServiceLocationEvent(self, external_id)
        # Add new entities to HA.
        self._async_add_entities([new_entity], True)

    async def _update_entity(self, external_id: str) -> None:
        """Update entity."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(external_id))

    async def _remove_entity(self, external_id: str) -> None:
        """Remove entity."""
        async_dispatcher_send(self._hass, SIGNAL_DELETE_ENTITY.format(external_id))
