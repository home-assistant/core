"""Support for generic GeoJSON events."""
from __future__ import annotations

import functools
import logging

import voluptuous as vol

from homeassistant.components.geo_location import PLATFORM_SCHEMA, GeolocationEvent
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_URL,
    LENGTH_KILOMETERS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GeoJsonEventsFeedEntityCoordinator
from ...helpers.entity_registry import async_get_registry
from .const import (
    ATTR_EXTERNAL_ID,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_RADIUS_IN_KM,
    DOMAIN,
    FEED,
    SOURCE,
)

_LOGGER = logging.getLogger(__name__)

# Deprecated.
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
    def async_add_geolocation(coordinator, config_entry_unique_id, external_id):
        """Add geolocation entity from feed."""
        new_entity = GeoJsonLocationEvent(
            coordinator, config_entry_unique_id, external_id
        )
        _LOGGER.debug("Adding geolocation %s", new_entity)
        async_add_entities([new_entity], False)

    coordinator.listeners.append(
        async_dispatcher_connect(
            hass, coordinator.async_event_new_entity(), async_add_geolocation
        )
    )
    # Initial generation of entries.
    if coordinator.data:
        _LOGGER.debug("Creating geolocation entities during setup")
        async_add_entities(
            GeoJsonLocationEvent(coordinator, entry.unique_id, external_id)
            for external_id in coordinator.data.keys()
        )
    _LOGGER.debug("Geolocation setup done")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GeoJSON Events platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class GeoJsonLocationEvent(CoordinatorEntity, GeolocationEvent):
    """This represents an external event with GeoJSON data."""

    coordinator: GeoJsonEventsFeedEntityCoordinator
    _attr_force_update = DEFAULT_FORCE_UPDATE
    _attr_unit_of_measurement = LENGTH_KILOMETERS
    _attr_icon = "mdi:pin"

    def __init__(
        self,
        coordinator: GeoJsonEventsFeedEntityCoordinator,
        config_entry_unique_id: str | None,
        external_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._external_id = external_id
        self._attr_unique_id = f"{config_entry_unique_id}_{external_id}"
        self._distance = None
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
        self._update_internal_state()

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        entity_registry = await async_get_registry(self.hass)
        # Remove from entity registry.
        if self.entity_id in entity_registry.entities:
            entity_registry.async_remove(self.entity_id)
            _LOGGER.debug("Removed geolocation %s from entity registry", self.entity_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.entry_available(self._external_id)

    @property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return self._distance

    def _update_internal_state(self):
        """Update state and attributes from coordinator data."""
        _LOGGER.debug("Updating %s from coordinator data", self._external_id)
        entry = self.coordinator.get_entry(self._external_id)
        if entry:
            self._attr_name = entry.title
            self._distance = entry.distance_to_home
            self._latitude = entry.coordinates[0]
            self._longitude = entry.coordinates[1]
            self._attr_extra_state_attributes = {ATTR_EXTERNAL_ID: self._external_id}
            # Add all properties from the feed entry.
            if entry.properties:
                for key, value in entry.properties.items():
                    self._attr_extra_state_attributes[f"Feature {key}"] = value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_internal_state()
        super()._handle_coordinator_update()

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
