"""Plugwise Switch component for HomeAssistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plugwise.constants import SwitchType

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class PlugwiseSwitchEntityDescription(SwitchEntityDescription):
    """Describes Plugwise switch entity."""

    key: SwitchType


SWITCHES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="dhw_cm_switch",
        translation_key="dhw_cm_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    PlugwiseSwitchEntityDescription(
        key="lock",
        translation_key="lock",
        entity_category=EntityCategory.CONFIG,
    ),
    PlugwiseSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    PlugwiseSwitchEntityDescription(
        key="cooling_ena_switch",
        translation_key="cooling_ena_switch",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseSwitchEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            if (switches := coordinator.data.devices[device_id].get("switches"))
            for description in SWITCHES
            if description.key in switches
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseSwitchEntity(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    entity_description: PlugwiseSwitchEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseSwitchEntityDescription,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.device["switches"][self.entity_description.key]

    @plugwise_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.device.get("members"),
            self.entity_description.key,
            "on",
        )

    @plugwise_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.device.get("members"),
            self.entity_description.key,
            "off",
        )
