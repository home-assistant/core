"""Support for various sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OpenThermWebCoordinator
from .const import DOMAIN
from .opentherm_controller import OpenThermController
from .opentherm_web_api import OpenThermWebApi

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="chw_active",
        name="Central Heating Water",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="dhw_active",
        name="Domestic Hot Water",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    coordinator: OpenThermWebCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    web_api: OpenThermWebApi = coordinator.data.web_api

    entities = []

    for description in SENSOR_TYPES:
        entities.append(OpenThermBinarySensor(coordinator, web_api, description))

    # Add all entities to HA
    async_add_entities(entities)


class OpenThermBinarySensor(
    CoordinatorEntity[OpenThermWebCoordinator], BinarySensorEntity
):
    """A sensor implementation for OpenTherm device."""

    controller: OpenThermController
    web_api: OpenThermWebApi

    def __init__(
        self,
        coordinator: OpenThermWebCoordinator,
        web_api: OpenThermWebApi,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator=coordinator, context=web_api)
        self.web_api = web_api
        self.controller = web_api.get_controller()
        self.entity_description = description  # type: ignore[assignment]
        self._attr_unique_id = f"{description.key}_{self.controller.device_id}"
        self._attr_name = description.name  # type: ignore[assignment]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.controller.device_id)},
            name="OpenThermWeb",
            manufacturer="Lake292",
        )
        self.refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        self.refresh()
        super()._handle_coordinator_update()

    def refresh(self) -> None:
        """Get the latest data and updates the states."""
        self.controller = self.coordinator.data.web_api.get_controller()
        if self.entity_description.key == "chw_active":
            self._attr_is_on = self.controller.chw_active
        elif self.entity_description.key == "dhw_active":
            self._attr_is_on = self.controller.dhw_active
