"""Support for the Hive switches."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import ATTR_MODE, DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="activeplug",
    ),
    SwitchEntityDescription(key="Heating_Heat_On_Demand"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("switch")
    entities = []
    if devices:
        for description in SWITCH_TYPES:
            for dev in devices:
                if dev["hiveType"] == description.key:
                    entities.append(HiveSwitch(hive, dev, description))
    async_add_entities(entities, True)


class HiveSwitch(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    def __init__(self, hive, hive_device, entity_description):
        """Initialise hive switch."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.hive.switch.turnOn(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hive.switch.turnOff(self.device)

    async def async_update(self):
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
