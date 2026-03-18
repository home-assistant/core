"""Water heater platform for Nest Heat Link."""

from __future__ import annotations

import datetime
from typing import Any

from homeassistant.components.water_heater import (
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.enums import HotWaterMode
from .pynest.models import NestHeatLink

PARALLEL_UPDATES = 0

MODE_SCHEDULE = "schedule"
MODE_BOOST = "boost"
MODE_BOOST_30M = "boost_30m"
MODE_BOOST_1H = "boost_1h"
MODE_BOOST_2H = "boost_2h"

# Boost duration mapping in seconds
BOOST_DURATIONS = {
    MODE_BOOST: 1800,  # 30 minutes (default)
    MODE_BOOST_30M: 1800,  # 30 minutes
    MODE_BOOST_1H: 3600,  # 1 hour
    MODE_BOOST_2H: 7200,  # 2 hours
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest water heater platform from a config entry."""
    coordinator = entry.runtime_data
    entities = [
        NestHeatLinkWaterHeater(coordinator, device)
        for device in coordinator.data.values()
        if isinstance(device, NestHeatLink)
    ]
    async_add_devices(entities)


class NestHeatLinkWaterHeater(NestEntity[NestHeatLink], WaterHeaterEntity):
    """Representation of a Nest Heat Link."""

    _attr_name = None  # Main feature of the device
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 30.0
    _attr_max_temp = 70.0
    _attr_translation_key = "heat_link"

    def __init__(self, coordinator: NestCoordinator, device: NestHeatLink) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator, device)
        if device.has_hot_water_control:
            self._attr_operation_list = [
                STATE_OFF,
                MODE_SCHEDULE,
                MODE_BOOST_30M,
                MODE_BOOST_1H,
                MODE_BOOST_2H,
            ]
        else:
            self._attr_operation_list = [STATE_OFF, MODE_SCHEDULE]

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        features = (
            WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.AWAY_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )
        if self.device.has_hot_water_temperature:
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        # Calculate remaining boost time
        current_time = dt_util.utcnow().timestamp()
        end_time = self.device.hot_water_boost_time_to_end

        # If the API returns 0 or a past time, boost is off
        if self.device.has_hot_water_control and end_time > current_time:
            remaining = end_time - current_time
            if remaining > 3600:
                return MODE_BOOST_2H
            if remaining > 1800:
                return MODE_BOOST_1H
            return MODE_BOOST_30M

        if self.device.hot_water_mode == HotWaterMode.SCHEDULE:
            return MODE_SCHEDULE

        return STATE_OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device.target_temperature

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return true if away mode is on."""
        return self.device.hot_water_away_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        attrs: dict[str, Any] = {
            "boiler_active": self.device.hot_water_active,
        }
        if self.device.hot_water_boost_time_to_end > 0:
            attrs["boost_timer_end"] = datetime.datetime.fromtimestamp(
                self.device.hot_water_boost_time_to_end, datetime.UTC
            )
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get("temperature")) is not None:
            await self._set_device_data({"hot_water_temperature": temp})

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if operation_mode == STATE_OFF:
            # Turn off schedule and cancel any active boost
            await self._set_device_data(
                {
                    "hot_water_mode": HotWaterMode.OFF.value,
                    "hot_water_boost": False,
                }
            )
        elif operation_mode == MODE_SCHEDULE:
            # Enable schedule and cancel any active boost
            await self._set_device_data(
                {
                    "hot_water_mode": HotWaterMode.SCHEDULE.value,
                    "hot_water_boost": False,
                }
            )
        elif operation_mode in BOOST_DURATIONS:
            await self._set_device_data(
                {
                    # Do not touch hot_water_mode - leave it as-is
                    "hot_water_mode": self.device.hot_water_mode.value,
                    # Activate boost (with specific or default duration)
                    "hot_water_boost": True,
                    "hot_water_boost_duration": BOOST_DURATIONS[operation_mode],
                }
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the water heater (activates schedule)."""
        await self.async_set_operation_mode(MODE_SCHEDULE)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the water heater."""
        await self.async_set_operation_mode(STATE_OFF)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self._set_device_data({"hot_water_away_enabled": True})

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._set_device_data({"hot_water_away_enabled": False})
