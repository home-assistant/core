"""Support for hive water heaters."""

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity, refresh_system
from .const import (
    ATTR_ONOFF,
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_BOOST_HOT_WATER,
    WATER_HEATER_MODES,
)

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
    if devices:
        async_add_entities((HiveWaterHeater(hive, dev) for dev in devices), True)

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

    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = SUPPORT_WATER_HEATER

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on hotwater."""
        await self.hive.hotwater.setMode(self.device, "MANUAL")

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn on hotwater."""
        await self.hive.hotwater.setMode(self.device, "OFF")

    @refresh_system
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        new_mode = HASS_TO_HIVE_STATE[operation_mode]
        await self.hive.hotwater.setMode(self.device, new_mode)

    @refresh_system
    async def async_hot_water_boost(self, time_period: int, on_off: str) -> None:
        """Handle the service call."""
        if on_off == "on":
            await self.hive.hotwater.setBoostOn(self.device, time_period)
        elif on_off == "off":
            await self.hive.hotwater.setBoostOff(self.device)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.hotwater.getWaterHeater(self.device)
        self._attr_available = self.device["deviceData"].get("online")
        if self._attr_available:
            self._attr_current_operation = HIVE_TO_HASS_STATE[
                self.device["status"]["current_operation"]
            ]
