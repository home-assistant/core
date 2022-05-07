"""Support for Big Ass Fans switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData


@dataclass
class BAFSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Device], bool]
    set_fn: Callable[[Device, bool], None]


@dataclass
class BAFSwitchEntityDescription(
    SwitchEntityDescription, BAFSwitchEntityDescriptionMixin
):
    """Describes BAF switch entity."""


def _set_fan_motion_auto(device: Device, value: bool) -> None:
    device.motion_sense_enable = value


MOTION_SWITCHES = [
    BAFSwitchEntityDescription(
        key="motion_sense",
        name="Motion Sense",
        value_fn=lambda device: cast(bool, device.motion_sense_enable),
        set_fn=_set_fan_motion_auto,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF fan switches."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    descriptions: list[BAFSwitchEntityDescription] = []
    descriptions.extend(MOTION_SWITCHES)
    async_add_entities(BAFSwitch(device, description) for description in descriptions)


class BAFSwitch(BAFEntity, SwitchEntity):
    """BAF switch component."""

    entity_description: BAFSwitchEntityDescription

    def __init__(self, device: Device, description: BAFSwitchEntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self.entity_description.value_fn(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self.entity_description.set_fn(self._device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self.entity_description.set_fn(self._device, False)
