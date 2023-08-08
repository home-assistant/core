"""Support for getting statistical data from a Pi-hole system."""
from __future__ import annotations

from hole import Hole

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN as PIHOLE_DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ads_blocked_today",
        translation_key="ads_blocked_today",
        native_unit_of_measurement="ads",
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key="ads_percentage_today",
        translation_key="ads_percentage_today",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key="clients_ever_seen",
        translation_key="clients_ever_seen",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    SensorEntityDescription(
        key="dns_queries_today",
        translation_key="dns_queries_today",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="domains_being_blocked",
        translation_key="domains_being_blocked",
        native_unit_of_measurement="domains",
        icon="mdi:block-helper",
    ),
    SensorEntityDescription(
        key="queries_cached",
        translation_key="queries_cached",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="queries_forwarded",
        translation_key="queries_forwarded",
        native_unit_of_measurement="queries",
        icon="mdi:comment-question-outline",
    ),
    SensorEntityDescription(
        key="unique_clients",
        translation_key="unique_clients",
        native_unit_of_measurement="clients",
        icon="mdi:account-outline",
    ),
    SensorEntityDescription(
        key="unique_domains",
        translation_key="unique_domains",
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
    _attr_has_entity_name = True

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

        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        try:
            return round(self.api.data[self.entity_description.key], 2)  # type: ignore[no-any-return]
        except TypeError:
            return self.api.data[self.entity_description.key]  # type: ignore[no-any-return]
