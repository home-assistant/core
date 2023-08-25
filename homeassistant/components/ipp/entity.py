"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get as er_async_get,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPDataUpdateCoordinator


@callback
def async_restore_sensor_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    coordinator: IPPDataUpdateCoordinator,
    sensors: Mapping[str, EntityDescription],
    sensor_class: Callable,
) -> None:
    """Restore sensor entities."""
    entities = []

    entity_registry = er_async_get(hass)
    entries = async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    domain = sensor_class.__module__.split(".")[-1]

    for entry in entries:
        if entry.domain != domain:
            continue

        id_len = len(coordinator.device_id) + 1
        attribute = entry.unique_id[id_len:]

        if description := sensors.get(attribute):
            entities.append(sensor_class(coordinator, description))

    if entities:
        async_add_entities(entities)


class IPPEntity(CoordinatorEntity[IPPDataUpdateCoordinator]):
    """Defines a base IPP entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IPPDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the IPP entity."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
        )
