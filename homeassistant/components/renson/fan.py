"""Platform to control a Renson ventilation unit."""
from __future__ import annotations

import logging
import math
from typing import Any

from renson_endura_delta.field_enum import CURRENT_LEVEL_FIELD, DataType
from renson_endura_delta.renson import Level, RensonVentilation

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DOMAIN,
    SET_BREEZE_SCHEMA,
    SET_DAY_NIGHT_TIME_SCHEMA,
    SET_POLLUTION_SETTINGS_SCHEMA,
    SET_TIMER_LEVEL_SCHEMA,
)
from .coordinator import RensonCoordinator
from .entity import RensonEntity

_LOGGER = logging.getLogger(__name__)

CMD_MAPPING = {
    0: Level.HOLIDAY,
    1: Level.LEVEL1,
    2: Level.LEVEL2,
    3: Level.LEVEL3,
    4: Level.LEVEL4,
}

SPEED_MAPPING = {
    Level.OFF.value: 0,
    Level.HOLIDAY.value: 0,
    Level.LEVEL1.value: 1,
    Level.LEVEL2.value: 2,
    Level.LEVEL3.value: 3,
    Level.LEVEL4.value: 4,
}


SPEED_RANGE: tuple[float, float] = (1, 4)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson fan platform."""

    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id].api
    coordinator: RensonCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    async_add_entities([RensonFan(api, coordinator)])

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "set_timer_level",
        SET_TIMER_LEVEL_SCHEMA,
        "set_timer_level",
    )

    platform.async_register_entity_service(
        "set_breeze", SET_BREEZE_SCHEMA, "set_breeze"
    )
    platform.async_register_entity_service(
        "set_day_night_time", SET_DAY_NIGHT_TIME_SCHEMA, "set_day_night_time"
    )
    platform.async_register_entity_service(
        "set_pollution_settings",
        SET_POLLUTION_SETTINGS_SCHEMA,
        "set_pollution_settings",
    )


class RensonFan(RensonEntity, FanEntity):
    """Representation of the Renson fan platform."""

    _attr_icon = "mdi:air-conditioner"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, api: RensonVentilation, coordinator: RensonCoordinator) -> None:
        """Initialize the Renson fan."""
        super().__init__("fan", api, coordinator)
        self._attr_speed_count = int_states_in_range(SPEED_RANGE)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        level = self.api.parse_value(
            self.api.get_field_value(self.coordinator.data, CURRENT_LEVEL_FIELD.name),
            DataType.LEVEL,
        )

        self._attr_percentage = ranged_value_to_percentage(
            SPEED_RANGE, SPEED_MAPPING[level]
        )

        super()._handle_coordinator_update()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            percentage = 1

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan (to away)."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        _LOGGER.debug("Changing fan speed percentage to %s", percentage)

        if percentage == 0:
            cmd = Level.HOLIDAY
        else:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            cmd = CMD_MAPPING[speed]

        await self.hass.async_add_executor_job(self.api.set_manual_level, cmd)

        await self.coordinator.async_request_refresh()

    async def set_timer_level(self, timer_level: str, time: int) -> None:
        """Set timer level."""
        level = Level[str(timer_level).upper()]

        await self.hass.async_add_executor_job(self.api.set_timer_level, level, time)

    async def set_breeze(self, call: ServiceCall) -> None:
        """Configure breeze feature."""
        level = call.data["breeze_level"]
        temperature = call.data["temperature"]
        activated = call.data["activate"]

        await self.hass.async_add_executor_job(
            self.api.set_breeze, level, temperature, activated
        )

    async def set_day_night_time(self, call: ServiceCall) -> None:
        """Configure day night times."""
        day = call.data["day"]
        night = call.data["night"]

        await self.hass.async_add_executor_job(self.api.set_time, day, night)

    async def set_pollution_settings(self, call: ServiceCall) -> None:
        """Configure pollutions settings."""
        day = call.data["day_pollution_level"]
        night = call.data["night_pollution_level"]
        humidity_control = call.data.get("humidity_control", False)
        airquality_control = call.data.get("airquality_control", False)
        co2_control = call.data.get("co2_control", False)
        co2_threshold = call.data.get("co2_threshold", 0)
        co2_hysteresis = call.data.get("co2_hysteresis", 0)

        await self.api.set_pollution(
            day,
            night,
            humidity_control,
            airquality_control,
            co2_control,
            co2_threshold,
            co2_hysteresis,
        )
