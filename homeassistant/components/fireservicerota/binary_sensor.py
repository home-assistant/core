"""Binary Sensor platform for FireServiceRota integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import FireServiceRotaClient
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN as FIRESERVICEROTA_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up FireServiceRota binary sensor based on a config entry."""

    client: FireServiceRotaClient = hass.data[FIRESERVICEROTA_DOMAIN][entry.entry_id][
        DATA_CLIENT
    ]

    coordinator: DataUpdateCoordinator = hass.data[FIRESERVICEROTA_DOMAIN][
        entry.entry_id
    ][DATA_COORDINATOR]

    async_add_entities([ResponseBinarySensor(coordinator, client, entry)])


class ResponseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an FireServiceRota sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "duty"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: FireServiceRotaClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.unique_id}_Duty"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self._client.on_duty

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return available attributes for binary sensor."""
        attr: dict[str, Any] = {}
        if not self.coordinator.data:
            return attr

        data = self.coordinator.data
        return {
            key: data[key]
            for key in (
                "start_time",
                "end_time",
                "available",
                "active",
                "assigned_function_ids",
                "skill_ids",
                "type",
                "assigned_function",
            )
            if key in data
        }
