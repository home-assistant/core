"""Support for Hydrawise sprinkler binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    hydrawise: Hydrawiser = coordinator.api

    entities = []

    for controller in hydrawise.controllers:
        for relay in controller.relays:
            entities.append(
                HydrawiseBinarySensor(
                    coordinator=coordinator,
                    controller_id=controller.controller_id,
                    relay_id=relay.relay_id,
                    description=BinarySensorEntityDescription(
                        key="is_watering",
                        name="Watering",
                        device_class=BinarySensorDeviceClass.MOISTURE,
                    ),
                )
            )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        relay_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator=coordinator,
            controller_id=controller_id,
            relay_id=relay_id,
            description=description,
        )
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""
        super()._handle_coordinator_update()
        self.update()

    def update(self) -> None:
        """Update state."""
        relay = self.coordinator.api.get_relay(self.controller_id, self.relay_id)
        if relay is None:
            return

        if self.entity_description.key == "is_watering":
            is_running = relay.is_zone_running()
            LOGGER.debug(
                "Updating IsWatering sensor for controller %d zone %s, is_wattering %s",
                self.controller_id,
                relay.name,
                is_running,
            )
            self._attr_is_on = is_running
