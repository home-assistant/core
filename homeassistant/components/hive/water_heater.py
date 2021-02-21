"""Support for hive water heaters."""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
    SUPPORT_OPERATION_MODE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, TEMP_CELSIUS
from homeassistant.helpers import config_validation as cv, entity_platform

from . import HiveEntity, refresh_system
from .const import ATTR_ONOFF, ATTR_TIME_PERIOD, DOMAIN, SERVICE_BOOST_HOT_WATER

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


BOOST_HOT_WATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_TIME_PERIOD, default="00:30:00"): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Required(ATTR_ONOFF): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive thermostat based on a config entry."""

    async def async_hot_water_boost(self, service):
        """Handle the service call."""
        entity_lookup = hass.data[DOMAIN]["entity_lookup"]
        device = entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not device:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        mode = service.data[ATTR_ONOFF]

        if mode == "on":
            await hive.hotwater.turn_boost_on(device, minutes)
        elif mode == "off":
            await hive.hotwater.turn_boost_off(device)

    hive = hass.data[DOMAIN]["entries"][entry.entry_id]
    devices = hive.session.devices.get("water_heater")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveWaterHeater(hive, dev))
    async_add_entities(entities, True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_BOOST_HOT_WATER,
        BOOST_HOT_WATER_SCHEMA,
        async_hot_water_boost,
    )


class HiveWaterHeater(HiveEntity, WaterHeaterEntity):
    """Hive Water Heater Device."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.device["device_id"])},
            "name": self.device["device_name"],
            "model": self.device["deviceData"]["model"],
            "manufacturer": self.device["deviceData"]["manufacturer"],
            "sw_version": self.device["deviceData"]["version"],
            "via_device": (DOMAIN, self.device["parentDevice"]),
        }

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
