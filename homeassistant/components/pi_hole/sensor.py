"""Support for getting statistical data from a Pi-hole system."""
from __future__ import annotations

from typing import Any

from hole import Hole

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN as PIHOLE_DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ads_blocked_today",
        name="Ads Blocked Today",
        native_unit_of_measurement="ads",
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key="ads_percentage_today",
        name="Ads Percentage Blocked Today",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key="clients_ever_seen",
        name="Seen Clients",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    SensorEntityDescription(
        key="dns_queries_today",
        name="DNS Queries Today",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="domains_being_blocked",
        name="Domains Blocked",
        native_unit_of_measurement="domains",
        icon="mdi:block-helper",
    ),
    SensorEntityDescription(
        key="queries_cached",
        name="DNS Queries Cached",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="queries_forwarded",
        name="DNS Queries Forwarded",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="unique_clients",
        name="DNS Unique Clients",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    SensorEntityDescription(
        key="unique_domains",
        name="DNS Unique Domains",
        native_unit_of_measurement="domains",
        icon="mdi:domain",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pi-hole sensor."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    sensors = [
        PiHoleSensor(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            entry.entry_id,
            description,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(PiHoleEntity, SensorEntity):
    """Representation of a Pi-hole sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{self._server_unique_id}/{description.name}"

    @property
    def native_value(self) -> Any:
        """Return the state of the device."""
        try:
            return round(self.api.data[self.entity_description.key], 2)
        except TypeError:
            return self.api.data[self.entity_description.key]
