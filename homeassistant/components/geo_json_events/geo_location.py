"""Support for generic GeoJSON events."""
from __future__ import annotations

import functools
import logging

from aio_geojson_generic_client import GenericFeedManager
import voluptuous as vol

from homeassistant.components.geo_location import PLATFORM_SCHEMA, GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    EVENT_HOMEASSISTANT_START,
    LENGTH_KILOMETERS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GeoJsonEventsFeedEntityCoordinator
from .const import (
    ATTR_EXTERNAL_ID,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_RADIUS_IN_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEED,
    SOURCE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GeoJSON Events platform."""
    coordinator = hass.data[DOMAIN][FEED][entry.entry_id]

    @callback
    def async_add_geolocation(feed_manager, config_entry_unique_id, external_id):
        """Add geolocation entity from feed."""
        new_entity = GeoJsonLocationEventNew(
            feed_manager, config_entry_unique_id, external_id
        )
        _LOGGER.debug("Adding geolocation %s", new_entity)
        async_add_entities([new_entity], True)

    coordinator.listeners.append(
        async_dispatcher_connect(
            hass, coordinator.async_event_new_entity(), async_add_geolocation
        )
    )
    _LOGGER.debug("Geolocation setup done")


class GeoJsonLocationEventNew(CoordinatorEntity, GeolocationEvent):
    """This represents an external event with GeoJSON data."""

    coordinator: GeoJsonEventsFeedEntityCoordinator
    # _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_force_update = DEFAULT_FORCE_UPDATE
    _attr_unit_of_measurement = LENGTH_KILOMETERS
    _attr_icon = "mdi:pin"

    def __init__(
        self,
        coordinator: GeoJsonEventsFeedEntityCoordinator,
        config_entry_unique_id: str,
        external_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._external_id = external_id
        self._attr_unique_id = f"{config_entry_unique_id}_{external_id}"
        self._state: StateType = None
        self._latitude = None
        self._longitude = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.url,
        )

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_delete_{self._external_id}",
                functools.partial(self.async_remove, force_remove=True),
            )
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        entry = self.coordinator.get_entry(self._external_id)
        if entry:
            _LOGGER.debug("Updating state from %s", entry)
            self._attr_name = entry.title
            self._latitude = entry.coordinates[0]
            self._longitude = entry.coordinates[1]
            distance = entry.distance_to_home
            if distance is not None:
                return round(distance, 1)
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        entry = self.coordinator.get_entry(self._external_id)
        if entry:
            attributes[ATTR_EXTERNAL_ID] = self._external_id
            # Add all properties from the feed entry.
            if entry.properties:
                for key, value in entry.properties.items():
                    attributes[f"Feature {key}"] = value
        return attributes


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GeoJSON Events platform."""
    url = config[CONF_URL]
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinates = (
        config.get(CONF_LATITUDE, hass.config.latitude),
        config.get(CONF_LONGITUDE, hass.config.longitude),
    )
    radius_in_km = config[CONF_RADIUS]
    # Initialize the entity manager.
    manager = GeoJsonFeedEntityManager(
        hass, async_add_entities, scan_interval, coordinates, url, radius_in_km
    )
    await manager.async_init()

    async def start_feed_manager(event=None):
        """Start feed manager."""
        await manager.async_update()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_feed_manager)


class GeoJsonFeedEntityManager:
    """Feed Entity Manager for GeoJSON feeds."""

    def __init__(
        self, hass, async_add_entities, scan_interval, coordinates, url, radius_in_km
    ):
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
        self._async_add_entities = async_add_entities
        self._scan_interval = scan_interval

    async def async_init(self):
        """Schedule initial and regular updates based on configured time interval."""

        async def update(event_time):
            """Update."""
            await self.async_update()

        # Trigger updates at regular intervals.
        async_track_time_interval(self._hass, update, self._scan_interval)
        _LOGGER.debug("Feed entity manager initialized")

    async def async_update(self):
        """Refresh data."""
        await self._feed_manager.update()
        _LOGGER.debug("Feed entity manager updated")

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    async def _generate_entity(self, external_id):
        """Generate new entity."""
        new_entity = GeoJsonLocationEvent(self, external_id)
        # Add new entities to HA.
        self._async_add_entities([new_entity], True)

    async def _update_entity(self, external_id):
        """Update entity."""
        async_dispatcher_send(self._hass, f"geo_json_events_update_{external_id}")

    async def _remove_entity(self, external_id):
        """Remove entity."""
        async_dispatcher_send(self._hass, f"geo_json_events_delete_{external_id}")


class GeoJsonLocationEvent(GeolocationEvent):
    """This represents an external event with GeoJSON data."""

    def __init__(self, feed_manager, external_id):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._name = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._remove_signal_delete = None
        self._remove_signal_update = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            f"geo_json_events_delete_{self._external_id}",
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            f"geo_json_events_update_{self._external_id}",
            self._update_callback,
        )

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self._remove_signal_delete()
        self._remove_signal_update()
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed for GeoJSON location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        self._name = feed_entry.title
        self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return f"NEW_{SOURCE}"

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._name

    @property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if not self._external_id:
            return {}
        return {ATTR_EXTERNAL_ID: self._external_id}
