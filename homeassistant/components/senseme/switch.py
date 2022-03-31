"""Support for Big Ass Fans SenseME switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from aiosenseme import SensemeFan
from aiosenseme.device import SensemeDevice

from homeassistant import config_entries
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SensemeEntity


@dataclass
class SenseMESwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[SensemeFan], bool]
    set_fn: Callable[[SensemeFan, bool], None]


@dataclass
class SenseMESwitchEntityDescription(
    SwitchEntityDescription, SenseMESwitchEntityDescriptionMixin
):
    """Describes SenseME switch entity."""


def _set_sleep_mode(device: SensemeDevice, value: bool) -> None:
    device.sleep_mode = value


def _set_motion_fan_auto(device: SensemeDevice, value: bool) -> None:
    device.motion_fan_auto = value


def _set_motion_light_auto(device: SensemeDevice, value: bool) -> None:
    device.motion_light_auto = value


FAN_SWITCHES = [
    # Turning on sleep mode will disable Whoosh
    SenseMESwitchEntityDescription(
        key="sleep_mode",
        name="Sleep Mode",
        value_fn=lambda device: cast(bool, device.sleep_mode),
        set_fn=_set_sleep_mode,
    ),
    SenseMESwitchEntityDescription(
        key="motion_fan_auto",
        name="Motion",
        value_fn=lambda device: cast(bool, device.motion_fan_auto),
        set_fn=_set_motion_fan_auto,
    ),
]

FAN_LIGHT_SWITCHES = [
    SenseMESwitchEntityDescription(
        key="motion_light_auto",
        name="Light Motion",
        value_fn=lambda device: cast(bool, device.motion_light_auto),
        set_fn=_set_motion_light_auto,
    ),
]

LIGHT_SWITCHES = [
    SenseMESwitchEntityDescription(
        key="sleep_mode",
        name="Sleep Mode",
        value_fn=lambda device: cast(bool, device.sleep_mode),
        set_fn=_set_sleep_mode,
    ),
    SenseMESwitchEntityDescription(
        key="motion_light_auto",
        name="Motion",
        value_fn=lambda device: cast(bool, device.motion_light_auto),
        set_fn=_set_motion_light_auto,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fans."""
    device = hass.data[DOMAIN][entry.entry_id]
    descriptions: list[SenseMESwitchEntityDescription] = []

    if device.is_fan:
        descriptions.extend(FAN_SWITCHES)
        if device.has_light:
            descriptions.extend(FAN_LIGHT_SWITCHES)
    elif device.is_light:
        descriptions.extend(LIGHT_SWITCHES)

    async_add_entities(
        HASensemeSwitch(device, description) for description in descriptions
    )


class HASensemeSwitch(SensemeEntity, SwitchEntity):
    """SenseME switch component."""

    entity_description: SenseMESwitchEntityDescription

    def __init__(
        self, device: SensemeFan, description: SenseMESwitchEntityDescription
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_device_class = SwitchDeviceClass.SWITCH
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.uuid}-SWITCH-{description.key}"

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
