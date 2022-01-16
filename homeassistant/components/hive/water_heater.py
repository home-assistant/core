"""Support for hive water heaters."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    SUPPORT_OPERATION_MODE,
    WaterHeaterEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import (
    ATTR_ONOFF,
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_BOOST_HOT_WATER,
    WATER_HEATER_MODES,
)

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("water_heater")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveWaterHeater(hive, dev))
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_BOOST_HOT_WATER,
        {
            vol.Optional(ATTR_TIME_PERIOD, default="00:30:00"): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            vol.Required(ATTR_ONOFF): vol.In(WATER_HEATER_MODES),
        },
        "async_hot_water_boost",
    )


class HiveWaterHeater(HiveEntity, WaterHeaterEntity):
    """Hive Water Heater Device."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            manufacturer=self.device["deviceData"]["manufacturer"],
            model=self.device["deviceData"]["model"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
            via_device=(DOMAIN, self.device["parentDevice"]),
        )

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
        await self.hive.hotwater.setMode(self.device, "MANUAL")

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn on hotwater."""
        await self.hive.hotwater.setMode(self.device, "OFF")

    @refresh_system
    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        new_mode = HASS_TO_HIVE_STATE[operation_mode]
        await self.hive.hotwater.setMode(self.device, new_mode)

    @refresh_system
    async def async_hot_water_boost(self, time_period, on_off):
        """Handle the service call."""
        if on_off == "on":
            await self.hive.hotwater.setBoostOn(self.device, time_period)
        elif on_off == "off":
            await self.hive.hotwater.setBoostOff(self.device)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.hotwater.getWaterHeater(self.device)
