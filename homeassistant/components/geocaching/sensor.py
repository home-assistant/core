"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import cast, override

from geocachingapi.models import GeocachingCache, GeocachingTrackable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_CODE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SUBENTRY_TYPE_TRACKED_CACHE
from .coordinator import (
    GeocachingConfigEntry,
    GeocachingCoordinatorData,
    GeocachingDataUpdateCoordinator,
)
from .entity import (
    GeocachingBaseEntity,
    GeocachingCacheEntity,
    GeocachingTrackableEntity,
)


@dataclass(frozen=True, kw_only=True)
class GeocachingSensorEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingCoordinatorData], str | int | None]


PROFILE_SENSORS: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="find_count",
        translation_key="find_count",
        value_fn=lambda status: status.user.find_count,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        translation_key="hide_count",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.hide_count,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        translation_key="favorite_points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        translation_key="souvenir_count",
        value_fn=lambda status: status.user.souvenir_count,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        translation_key="awarded_favorite_points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.awarded_favorite_points,
    ),
)


@dataclass(frozen=True, kw_only=True)
class GeocachingCacheSensorDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingCache], StateType | datetime.date]


@dataclass(frozen=True, kw_only=True)
class GeocachingTrackableSensorDescription(SensorEntityDescription):
    """Define trackable sensor entity description class."""

    value_fn: Callable[[GeocachingTrackable], StateType | datetime.date]


CACHE_SENSORS: tuple[GeocachingCacheSensorDescription, ...] = (
    GeocachingCacheSensorDescription(
        key="found_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.found_date_time,
    ),
    GeocachingCacheSensorDescription(
        key="favorite_points",
        value_fn=lambda cache: cache.favorite_points,
    ),
    GeocachingCacheSensorDescription(
        key="hidden_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda cache: cache.hidden_date,
    ),
)

TRACKABLE_SENSORS: tuple[GeocachingTrackableSensorDescription, ...] = (
    GeocachingTrackableSensorDescription(
        key="kilometers_traveled",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda trackable: trackable.kilometers_traveled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeocachingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        GeocachingProfileSensor(coordinator, description)
        for description in PROFILE_SENSORS
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_TRACKED_CACHE):
        reference_code = subentry.data[CONF_CODE].strip().upper()
        if (cache := coordinator.data.tracked_caches.get(reference_code)) is None:
            continue
        async_add_entities(
            (
                GeoEntityCacheSensorEntity(
                    coordinator, cache, reference_code, description
                )
                for description in CACHE_SENSORS
            ),
            config_subentry_id=subentry.subentry_id,
        )

    async_add_entities(
        GeoEntityTrackableSensorEntity(coordinator, trackable, description)
        for trackable in coordinator.data.trackables.values()
        for description in TRACKABLE_SENSORS
    )


# Base class for a cache entity.
# Sets the device, ID and translation settings to correctly
# group the entity to the correct cache device and give it
# the correct name.
class GeoEntityBaseCache(GeocachingCacheEntity, SensorEntity):
    """Base class for cache entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        reference_code: str,
        key: str,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, reference_code)

        self._attr_unique_id = f"{self._reference_code}_{key}"

        # The translation key determines the name of the entity
        # as this is the lookup for the `strings.json` file.
        self._attr_translation_key = f"cache_{key}"


class GeoEntityCacheSensorEntity(GeoEntityBaseCache, SensorEntity):
    """Representation of a cache sensor."""

    entity_description: GeocachingCacheSensorDescription

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        cache: GeocachingCache,
        reference_code: str,
        description: GeocachingCacheSensorDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator, cache, reference_code, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.cache)


class GeoEntityBaseTrackable(GeocachingTrackableEntity, SensorEntity):
    """Base class for trackable entities."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
        key: str,
    ) -> None:
        """Initialize the Geocaching trackable sensor."""
        super().__init__(coordinator, trackable)

        account_reference_code = cast(str, coordinator.data.user.reference_code)
        self._attr_unique_id = f"{account_reference_code}_{self._reference_code}_{key}"
        self._attr_translation_key = f"trackable_{key}"


class GeoEntityTrackableSensorEntity(GeoEntityBaseTrackable, SensorEntity):
    """Representation of a trackable sensor."""

    entity_description: GeocachingTrackableSensorDescription

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        trackable: GeocachingTrackable,
        description: GeocachingTrackableSensorDescription,
    ) -> None:
        """Initialize the Geocaching trackable sensor."""
        super().__init__(coordinator, trackable, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime.date:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.trackable)


class GeocachingProfileSensor(GeocachingBaseEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: GeocachingSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        description: GeocachingSensorEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.user.reference_code}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            name=f"Geocaching {coordinator.data.user.username}",
            identifiers={(DOMAIN, cast(str, coordinator.data.user.reference_code))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Groundspeak, Inc.",
        )

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
