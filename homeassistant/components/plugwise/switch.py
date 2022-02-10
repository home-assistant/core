"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="relay",
        name="Relay",
        icon="mdi:electric-switch",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[PlugwiseSwitchEntity] = []
    for device_id, device in coordinator.data.devices.items():
        for description in SWITCHES:
            if "switches" not in device or description.key not in device["switches"]:
                continue
            entities.append(PlugwiseSwitchEntity(coordinator, device_id, description))
    async_add_entities(entities)


class PlugwiseSwitchEntity(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"
        self._attr_name = coordinator.data.devices[device_id].get("name")

    @plugwise_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.coordinator.data.devices[self._dev_id].get("members"),
            self.entity_description.key,
            "on",
        )

    @plugwise_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.coordinator.data.devices[self._dev_id].get("members"),
            self.entity_description.key,
            "off",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
            super()._handle_coordinator_update()
            return

        self._attr_is_on = data["switches"].get(self.entity_description.key)
        super()._handle_coordinator_update()
