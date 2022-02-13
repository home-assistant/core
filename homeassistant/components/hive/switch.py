"""Support for the Hive switches."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import ATTR_MODE, DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


@dataclass
class HiveSwitchrEntityDescription(SwitchEntityDescription):
    """Class describing Hive sensor entities."""

    value: Callable = round


SWITCH_TYPES: tuple[HiveSwitchrEntityDescription, ...] = (
    HiveSwitchrEntityDescription(
        key="activeplug",
    ),
    HiveSwitchrEntityDescription(
        key="Heating_Heat_On_Demand", entity_category=EntityCategory.CONFIG
    ),
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

    entity_description: HiveSwitchrEntityDescription

    def __init__(self, hive, hive_device, description):
        """Intiate Hive Switch."""
        super().__init__(hive, hive_device)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            manufacturer=self.device["deviceData"]["manufacturer"],
            model=self.device["deviceData"]["model"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
            via_device=(DOMAIN, self.device["parentDevice"]),
        )
        self._attr_name = self.device["haName"]
        self.entity_description = description

    @property
    def available(self):
        """Return if the device is available."""
        return self.device["deviceData"].get("online")

    @property
    def extra_state_attributes(self):
        """Show Device Attributes."""
        return {
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.device["status"].get("power_usage")

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device["status"]["state"]

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
