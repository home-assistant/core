"""Support for getting statistical data from a Pi-hole system."""

from __future__ import annotations

from hole import Hole

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import CONF_API_VERSION, PiHoleConfigEntry
from .entity import PiHoleEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ads_blocked_today",
        translation_key="ads_blocked_today",
    ),
    SensorEntityDescription(
        key="ads_percentage_today",
        translation_key="ads_percentage_today",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="clients_ever_seen",
        translation_key="clients_ever_seen",
    ),
    SensorEntityDescription(
        key="dns_queries_today", translation_key="dns_queries_today"
    ),
    SensorEntityDescription(
        key="domains_being_blocked",
        translation_key="domains_being_blocked",
    ),
    SensorEntityDescription(key="queries_cached", translation_key="queries_cached"),
    SensorEntityDescription(
        key="queries_forwarded", translation_key="queries_forwarded"
    ),
    SensorEntityDescription(key="unique_clients", translation_key="unique_clients"),
    SensorEntityDescription(key="unique_domains", translation_key="unique_domains"),
)
SENSOR_TYPES_V6: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="queries.blocked",
        translation_key="ads_blocked",
    ),
    SensorEntityDescription(
        key="queries.percent_blocked",
        translation_key="percent_ads_blocked",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="clients.total",
        translation_key="clients_ever_seen",
    ),
    SensorEntityDescription(key="queries.total", translation_key="dns_queries"),
    SensorEntityDescription(
        key="gravity.domains_being_blocked",
        translation_key="domains_being_blocked",
    ),
    SensorEntityDescription(key="queries.cached", translation_key="queries_cached"),
    SensorEntityDescription(
        key="queries.forwarded", translation_key="queries_forwarded"
    ),
    SensorEntityDescription(key="clients.active", translation_key="unique_clients"),
    SensorEntityDescription(
        key="queries.unique_domains", translation_key="unique_domains"
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole sensor."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data
    sensors = [
        PiHoleSensor(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in (
            SENSOR_TYPES if entry.data[CONF_API_VERSION] == 5 else SENSOR_TYPES_V6
        )
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(PiHoleEntity, SensorEntity):
    """Representation of a Pi-hole sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        try:
            return round(get_nested(self.api.data, self.entity_description.key), 2)  # type: ignore[no-any-return]
        except TypeError:
            return get_nested(self.api.data, self.entity_description.key)  # type: ignore[no-any-return]


def get_nested(data: dict, key: str) -> float | int:
    """Get a value from a nested dictionary using a dot-separated key."""
    for part in key.split("."):
        if not isinstance(data, dict):
            raise KeyError(f"Cannot access '{part}' in non-dict {data}")
        data = data[part]
    return data
