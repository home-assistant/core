"""Support for interface with a Gree climate systems."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from greeclimate.device import Device

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DISPATCHERS, DOMAIN
from .entity import GreeEntity


@dataclass
class GreeRequiredKeysMixin:
    """Mixin for required keys."""

    get_value_fn: Callable[[Device], bool]
    set_value_fn: Callable[[Device, bool], None]


@dataclass
class GreeSwitchEntityDescription(SwitchEntityDescription, GreeRequiredKeysMixin):
    """Describes Gree switch entity."""

    # GreeSwitch does not support UNDEFINED or None,
    # restrict the type to str.
    name: str = ""


def _set_light(device: Device, value: bool) -> None:
    """Typed helper to set device light property."""
    device.light = value


def _set_quiet(device: Device, value: bool) -> None:
    """Typed helper to set device quiet property."""
    device.quiet = value


def _set_fresh_air(device: Device, value: bool) -> None:
    """Typed helper to set device fresh_air property."""
    device.fresh_air = value


def _set_xfan(device: Device, value: bool) -> None:
    """Typed helper to set device xfan property."""
    device.xfan = value


def _set_anion(device: Device, value: bool) -> None:
    """Typed helper to set device anion property."""
    device.anion = value


GREE_SWITCHES: tuple[GreeSwitchEntityDescription, ...] = (
    GreeSwitchEntityDescription(
        icon="mdi:lightbulb",
        name="Panel Light",
        key="light",
        get_value_fn=lambda d: d.light,
        set_value_fn=_set_light,
    ),
    GreeSwitchEntityDescription(
        name="Quiet",
        key="quiet",
        get_value_fn=lambda d: d.quiet,
        set_value_fn=_set_quiet,
    ),
    GreeSwitchEntityDescription(
        name="Fresh Air",
        key="fresh_air",
        get_value_fn=lambda d: d.fresh_air,
        set_value_fn=_set_fresh_air,
    ),
    GreeSwitchEntityDescription(
        name="XFan",
        key="xfan",
        get_value_fn=lambda d: d.xfan,
        set_value_fn=_set_xfan,
    ),
    GreeSwitchEntityDescription(
        icon="mdi:pine-tree",
        name="Health mode",
        key="anion",
        get_value_fn=lambda d: d.anion,
        set_value_fn=_set_anion,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gree HVAC device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""

        async_add_entities(
            GreeSwitch(coordinator=coordinator, description=description)
            for description in GREE_SWITCHES
        )

    for coordinator in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordinator)

    hass.data[DOMAIN][DISPATCHERS].append(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class GreeSwitch(GreeEntity, SwitchEntity):
    """Generic Gree switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: GreeSwitchEntityDescription

    def __init__(self, coordinator, description: GreeSwitchEntityDescription) -> None:
        """Initialize the Gree device."""
        self.entity_description = description

        super().__init__(coordinator, description.name)

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.entity_description.get_value_fn(self.coordinator.device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.entity_description.set_value_fn(self.coordinator.device, True)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.entity_description.set_value_fn(self.coordinator.device, False)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
