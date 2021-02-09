"""Support for the Hive switches."""
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity

from . import ATTR_AVAILABLE, ATTR_MODE, DATA_HIVE, DOMAIN, HiveEntity, refresh_system

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Hive Switch."""
    if discovery_info is None:
        return

    hive = hass.data[DOMAIN].get(DATA_HIVE)
    devices = hive.devices.get("switch")
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
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.device["haName"]

    @property
    def available(self):
        """Return if the device is available."""
        return self.device["deviceData"].get("online")

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return {
            ATTR_AVAILABLE: self.attributes.get(ATTR_AVAILABLE),
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.device["status"]["power_usage"]

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device["status"]["state"]

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.device["hiveType"] == "activeplug":
            await self.hive.switch.turn_on(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self.device["hiveType"] == "activeplug":
            await self.hive.switch.turn_off(self.device)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.switch.get_plug(self.device)
