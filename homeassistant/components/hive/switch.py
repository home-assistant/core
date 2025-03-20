"""Support for the Hive switches."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from apyhiveapi import Hive

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import refresh_system
from .const import ATTR_MODE, DOMAIN
from .entity import HiveEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="activeplug",
    ),
    SwitchEntityDescription(
        key="Heating_Heat_On_Demand",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("switch")
    if not devices:
        return
    async_add_entities(
        (
            HiveSwitch(hive, dev, description)
            for dev in devices
            for description in SWITCH_TYPES
            if dev["hiveType"] == description.key
        ),
        True,
    )


class HiveSwitch(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    def __init__(
        self,
        hive: Hive,
        hive_device: dict[str, Any],
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialise hive switch."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hive.switch.turnOn(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.hive.switch.turnOff(self.device)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.switch.getSwitch(self.device)
        self.attributes.update(self.device.get("attributes", {}))
        self._attr_extra_state_attributes = {
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }
        self._attr_available = self.device["deviceData"].get("online")
        if self._attr_available:
            self._attr_is_on = self.device["status"]["state"]
