"""Support for hive water heaters."""

from datetime import timedelta

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
    SUPPORT_OPERATION_MODE,
    WaterHeaterEntity,
)
from homeassistant.const import TEMP_CELSIUS

from . import DATA_HIVE, DOMAIN, HiveEntity, refresh_system

SUPPORT_FLAGS_HEATER = SUPPORT_OPERATION_MODE
HOTWATER_NAME = "Hot Water"
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
HIVE_TO_HASS_STATE = {
    "SCHEDULE": STATE_ECO,
    "ON": STATE_ON,
    "OFF": STATE_OFF,
}

HASS_TO_HIVE_STATE = {
    STATE_ECO: "SCHEDULE",
    STATE_ON: "MANUAL",
    STATE_OFF: "OFF",
}

SUPPORT_WATER_HEATER = [STATE_ECO, STATE_ON, STATE_OFF]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Hive Hotwater."""
    if discovery_info is None:
        return

    hive = hass.data[DOMAIN].get(DATA_HIVE)
    devices = hive.devices.get("water_heater")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveWaterHeater(hive, dev))
    async_add_entities(entities, True)


class HiveWaterHeater(HiveEntity, WaterHeaterEntity):
    """Hive Water Heater Device."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def name(self):
        """Return the name of the water heater."""
        return HOTWATER_NAME

    @property
    def available(self):
        """Return if the device is available."""
        return self.device["deviceData"]["online"]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation."""
        return HIVE_TO_HASS_STATE[self.device["status"]["current_operation"]]

    @property
    def operation_list(self):
        """List of available operation modes."""
        return SUPPORT_WATER_HEATER

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn on hotwater."""
        await self.hive.hotwater.set_mode(self.device, "MANUAL")

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn on hotwater."""
        await self.hive.hotwater.set_mode(self.device, "OFF")

    @refresh_system
    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        new_mode = HASS_TO_HIVE_STATE[operation_mode]
        await self.hive.hotwater.set_mode(self.device, new_mode)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.hotwater.get_hotwater(self.device)
