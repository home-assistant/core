"""Asus Router entity module."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import helpers
from .const import COORDINATOR, DOMAIN, ROUTER
from .dataclass import AREntityDescription
from .router import ARDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_ar_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    sensors: list[AREntityDescription],
    sensor_class: type[AREntity],
) -> None:
    """Set up Asus Router entities."""

    router: ARDevice = hass.data[DOMAIN][entry.entry_id][ROUTER]
    entities = []

    for sensor_data in router.sensor_coordinator.values():
        coordinator = sensor_data[COORDINATOR]
        for sensor_description in sensors:
            try:
                sensor_type = sensor_description.key_group
                if sensor_type in sensor_data:
                    if sensor_description.key in sensor_data[sensor_type]:
                        entities.append(
                            sensor_class(coordinator, router, sensor_description)
                        )
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.warning(ex)

    async_add_entities(entities, True)


class AREntity(CoordinatorEntity):
    """Asus Router entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: ARDevice,
        description: AREntityDescription,
    ) -> None:
        """Initialize Asus Router entity."""

        super().__init__(coordinator)
        self.router = router
        self.api = router.bridge.api
        self.coordinator = coordinator

        self._attr_name = f"{router._conf_name} {description.name}"
        self._attr_unique_id = helpers.to_unique_id(
            f"{DOMAIN}_{router.mac}_{description.name}"
        )
        self._attr_device_info = router.device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""

        # Check if description is of the needed class
        if not isinstance(self.entity_description, AREntityDescription):
            return {}

        description = self.entity_description
        _attributes = description.extra_state_attributes
        if not _attributes:
            return {}

        attributes = {}

        for attr in _attributes:
            if attr in self.coordinator.data:
                attributes[_attributes[attr]] = self.coordinator.data[attr]

        return dict(sorted(attributes.items())) or {}
