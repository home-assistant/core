"""Sensor platform for Discogs."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import DiscogsConfigEntry, DiscogsData, DiscogsDataUpdateCoordinator

UNIT_RECORDS = "records"


@dataclass(frozen=True, kw_only=True)
class DiscogsSensorEntityDescription(SensorEntityDescription):
    """Describes a Discogs sensor entity."""

    value_fn: Callable[[DiscogsData], str | int | None]
    attrs_fn: Callable[[DiscogsData], dict[str, Any] | None]


SENSOR_TYPES: tuple[DiscogsSensorEntityDescription, ...] = (
    DiscogsSensorEntityDescription(
        key="collection",
        translation_key="collection",
        native_unit_of_measurement=UNIT_RECORDS,
        value_fn=lambda data: data.collection_count,
        attrs_fn=lambda _: None,
    ),
    DiscogsSensorEntityDescription(
        key="wantlist",
        translation_key="wantlist",
        native_unit_of_measurement=UNIT_RECORDS,
        value_fn=lambda data: data.wantlist_count,
        attrs_fn=lambda _: None,
    ),
    DiscogsSensorEntityDescription(
        key="random_record",
        translation_key="random_record",
        value_fn=lambda data: data.random_record,
        attrs_fn=lambda data: data.random_record_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiscogsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Discogs sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        DiscogsSensor(coordinator, description, entry.entry_id)
        for description in SENSOR_TYPES
    )


class DiscogsSensor(CoordinatorEntity[DiscogsDataUpdateCoordinator], SensorEntity):
    """Representation of a Discogs sensor."""

    entity_description: DiscogsSensorEntityDescription
    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DiscogsDataUpdateCoordinator,
        description: DiscogsSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.discogs.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attrs_fn(self.coordinator.data)
