"""Support for Krisinformation.se Feeds."""
from __future__ import annotations

from datetime import timedelta
import logging
from collections.abc import Callable

from krisinformation import KrisinformationFeedEntry, KrisinformationFeedManager
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.geo_location import PLATFORM_SCHEMA, GeolocationEvent
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
    UnitOfLength,
)
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send


_LOGGER = logging.getLogger(__name__)
DOMAIN =  "krisinformation"

SCAN_INTERVAL = timedelta(seconds=120)
DEFAULT_RADIUS_IN_KM = 50.0
SOURCE = "krisinformation"

# Set of rules that define what configuration options are
# required or allowed for a particular platform within Home Assistant
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    }
)


async def setup_platform(
    hass: HomeAssistant,
    config: ConfigType, #Ändra denna till ConfigEntry?
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Krisinformation.se Feed platform."""
    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    coordinates: tuple[float, float] = (
        config.get(CONF_LATITUDE, hass.config.latitude),
        config.get(CONF_LONGITUDE, hass.config.longitude),
    )
    radius_in_km: float = config[CONF_RADIUS]

    # Initialize the entity manager.
    entity_manager = KrisinformationFeedEntityManager(
        hass, add_entities, scan_interval, coordinates, radius_in_km
    )

    def start_feed_manager(event: Event) -> None:
        """Start feed manager."""
        entity_manager.startup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_feed_manager)


# This might be more correct to use
#async def async_setup_entry(
#    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
#) -> None:
#    """Set up the Krisinformation feed platform."""
#    manager: KrisinformationFeedEntityManager = hass.data[DOMAIN][FEED][entry.entry_id]
#
#    @callback
#    def async_add_geolocation(
#        feed_manager: KrisinformationFeedEntityManager,
#        integration_id: str,
#        external_id: str,
#    ) -> None:
#        """Add geolocation entity from feed."""
#        new_entity = KrisinformationLocationEvent(feed_manager, external_id)
#        _LOGGER.debug("Adding geolocation %s", new_entity)
#        async_add_entities([new_entity], True)
#
#    manager.listeners.append(
#        async_dispatcher_connect(hass, manager.signal_new_entity, async_add_geolocation)
#    )
#    # Do not wait for update here so that the setup can be completed and because an
#    # update will fetch data from the feed via HTTP and then process that data.
#    entry.async_create_task(hass, manager.async_update()) #Either this
#    hass.ascync_create_task(manager.async_update()) #Or this
#    _LOGGER.debug("Geolocation setup done")


class KrisinformationFeedEntityManager:
    """Feed Entity Manager for Krisinformation.se feed."""

    def __init__(
        self,
        hass: HomeAssistant,
        add_entities: AddEntitiesCallback,
        scan_interval: timedelta,
        coordinates: tuple[float, float],
        radius_in_km: float,
    ) -> None:
        """Initialize the Feed Entity Manager."""
        self._hass = hass
        self._feed_manager = KrisinformationFeedManager(
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            radius_in_km,
        )
        self._add_entities = add_entities
        self._scan_interval = scan_interval
        self._coordinates = coordinates
        self._radius_in_km = radius_in_km
       # self._entities: list[KrisinformationFeedEntity] = []

    def startup(self) -> None:
        """Start up this manager."""
        self._feed_manager.startup(self._scan_interval)

    def get_entry(self, unique_id: str) -> KrisinformationFeedEntry | None:
        """Get a feed entry."""
        return self._feed_manager.get_entry(unique_id)

    def _generate_entity(self, unique_id: str) -> None:
        """Generate new entity."""
        new_entity = KrisinformationLocationEvent(self, unique_id)
        # Add new entities to HA
        self._add_entities([new_entity], True)

    def _update_entity(self, unique_id: str) -> None:
        """Update entity."""
        self._feed_manager.update()

    def _remove_entity(self, unique_id: str) -> None:
        """Remove entity."""


class KrisinformationLocationEvent(GeolocationEvent):
    """Representation of a Krisinformation.se location event."""

    _attr_icon = "mdi:alert"
    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(
        self, feed_manager: KrisinformationFeedEntityManager, external_id: str
    ) -> None:
        """Initialize entity with data from feed entry"""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]
        feed_entry = self._feed_manager.get_entry(external_id)
        if feed_entry:
            self._latitude = feed_entry.latitude
            self._longitude = feed_entry.longitude

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            #SIGNAL_DELETE_ENTITY.format(self._external_id),
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            #SIGNAL_UPDATE_ENTITY.format(self._external_id),
            self._update_callback,
        )

    @callback
    def _delete_callback(self) -> None:
        """Remove this entity."""
        self._remove_signal_delete()
        self._remove_signal_update()
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _update_callback(self) -> None:
        """Update entity."""
        self.async_schedule_update_ha_state(True)

    @callback
    def _generate_callback(self) -> None:
        """Generate entity."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    async def async_update(self) -> None:
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the event."""
        return self._longitude

