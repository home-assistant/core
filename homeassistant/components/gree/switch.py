"""Support for interface with a Gree climate systems."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from greeclimate.device import Props

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DISPATCHERS, DOMAIN
from .entity import GreeEntity


@dataclass
class GreeSwitchRequiredKeysMixin:
    """Mixin for require keys."""

    property: Props


@dataclass
class GreeSwitchEntityDescription(SwitchEntityDescription, GreeSwitchRequiredKeysMixin):
    """Describes a switch entity."""


GREE_SWITCHES: tuple[GreeSwitchEntityDescription, ...] = (
    GreeSwitchEntityDescription(
        icon="mdi:lightbulb",
        name="Panel Light",
        key="panel_light",
        property=Props.LIGHT,
    ),
    GreeSwitchEntityDescription(
        name="Quiet",
        key="quiet",
        property=Props.QUIET,
    ),
    GreeSwitchEntityDescription(
        name="Fresh Air",
        key="fresh_air",
        property=Props.FRESH_AIR,
    ),
    GreeSwitchEntityDescription(name="XFan", key="xfan", property=Props.XFAN),
    GreeSwitchEntityDescription(
        icon="mdi:pine-tree",
        name="Health mode",
        key="health_mode",
        property=Props.ANION,
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
    """Generic Gree entity to use with a modern style configuration."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: GreeSwitchEntityDescription

    def __init__(self, coordinator, description: GreeSwitchEntityDescription) -> None:
        """Initialize the Gree device."""
        self.entity_description = description

        super().__init__(coordinator, cast(str, description.name))

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.coordinator.device.get_property(self.entity_description.property)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        setattr(self.coordinator.device, self.entity_description.key, True)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.coordinator.device.set_property(self.entity_description.property, 0)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
