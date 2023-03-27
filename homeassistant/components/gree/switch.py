"""Support for interface with a Gree climate systems."""
from __future__ import annotations

from typing import Any, cast

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

GREE_SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        icon="mdi:lightbulb",
        name="Panel Light",
        key="light",
    ),
    SwitchEntityDescription(
        name="Quiet",
        key="quiet",
    ),
    SwitchEntityDescription(
        name="Fresh Air",
        key="fresh_air",
    ),
    SwitchEntityDescription(name="XFan", key="xfan"),
    SwitchEntityDescription(
        icon="mdi:pine-tree",
        name="Health mode",
        key="anion",
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

    def __init__(self, coordinator, description: SwitchEntityDescription) -> None:
        """Initialize the Gree device."""
        self.entity_description = description

        super().__init__(coordinator, cast(str, description.name))

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return getattr(self.coordinator.device, self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        setattr(self.coordinator.device, self.entity_description.key, True)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        setattr(self.coordinator.device, self.entity_description.key, False)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
