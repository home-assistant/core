"""Support for the Hive switches."""
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity

from . import HiveEntity, refresh_system
from .const import ATTR_MODE, DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("switch")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveDevicePlug(hive, dev))
    async_add_entities(entities, True)


class HiveDevicePlug(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        if self.device["hiveType"] == "activeplug":
            return {
                "identifiers": {(DOMAIN, self.device["device_id"])},
                "name": self.device["device_name"],
                "model": self.device["deviceData"]["model"],
                "manufacturer": self.device["deviceData"]["manufacturer"],
                "sw_version": self.device["deviceData"]["version"],
                "via_device": (DOMAIN, self.device["parentDevice"]),
            }

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.device["haName"]

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
