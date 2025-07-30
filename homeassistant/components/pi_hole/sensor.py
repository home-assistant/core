"""Support for getting statistical data from a Pi-hole system."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hole import Hole

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleConfigEntry
from .entity import PiHoleEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ads_blocked_today",
        translation_key="ads_blocked_today",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="ads_percentage_today",
        translation_key="ads_percentage_today",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="clients_ever_seen",
        translation_key="clients_ever_seen",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="dns_queries_today",
        translation_key="dns_queries_today",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="domains_being_blocked",
        translation_key="domains_being_blocked",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries_cached",
        translation_key="queries_cached",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries_forwarded",
        translation_key="queries_forwarded",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="unique_clients",
        translation_key="unique_clients",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="unique_domains",
        translation_key="unique_domains",
        suggested_display_precision=0,
    ),
)

SENSOR_TYPES_V6: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="queries.blocked",
        translation_key="ads_blocked",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries.percent_blocked",
        translation_key="percent_ads_blocked",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="clients.total",
        translation_key="clients_ever_seen",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries.total",
        translation_key="dns_queries",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="gravity.domains_being_blocked",
        translation_key="domains_being_blocked",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries.cached",
        translation_key="queries_cached",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries.forwarded",
        translation_key="queries_forwarded",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="clients.active",
        translation_key="unique_clients",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="queries.unique_domains",
        translation_key="unique_domains",
        suggested_display_precision=0,
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
            SENSOR_TYPES if hole_data.api_version == 5 else SENSOR_TYPES_V6
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
        return get_nested(self.api.data, self.entity_description.key)


def get_nested(data: Mapping[str, Any], key: str) -> float | int:
    """Get a value from a nested dictionary using a dot-separated key.

    Ensures type safety as it iterates into the dict.
    """
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, Mapping):
            raise KeyError(f"Cannot access '{part}' in non-dict {current!r}")
        current = current[part]
    if not isinstance(current, (float, int)):
        raise TypeError(f"Value at '{key}' is not a float or int: {current!r}")
    return current
