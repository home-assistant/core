"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from plugwise import SmileSwitches

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command


@dataclass
class PlugwiseSwitchBaseMixin:
    """Mixin for required Plugwise switch description keys."""

    value_fn: Callable[[SmileSwitches], bool]


@dataclass
class PlugwiseSwitchEntityDescription(SwitchEntityDescription, PlugwiseSwitchBaseMixin):
    """Describes Plugwise switch entity."""


SWITCHES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="dhw_cm_switch",
        translation_key="dhw_cm_switch",
        icon="mdi:water-plus",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data["dhw_cm_switch"],
    ),
    PlugwiseSwitchEntityDescription(
        key="lock",
        translation_key="lock",
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data["lock"],
    ),
    PlugwiseSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda data: data["relay"],
    ),
    PlugwiseSwitchEntityDescription(
        key="cooling_ena_switch",
        name="Cooling",
        icon="mdi:snowflake-thermometer",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data["cooling_ena_switch"],
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
        if not (switches := device.get("switches")):
            continue
        for description in SWITCHES:
            if description.key not in switches:
                continue
            entities.append(PlugwiseSwitchEntity(coordinator, device_id, description))
    async_add_entities(entities)


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
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_description.value_fn(self.device["switches"])

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
