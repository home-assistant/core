"""Platform to control a Renson ventilation unit."""

from __future__ import annotations

import logging
import math
from typing import Any

from renson_endura_delta.field_enum import (
    BREEZE_LEVEL_FIELD,
    BREEZE_TEMPERATURE_FIELD,
    CURRENT_LEVEL_FIELD,
    DataType,
)
from renson_endura_delta.renson import Level, RensonVentilation
import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import DOMAIN
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
    Level.BREEZE.value: 0,
    Level.LEVEL1.value: 1,
    Level.LEVEL2.value: 2,
    Level.LEVEL3.value: 3,
    Level.LEVEL4.value: 4,
}

SET_TIMER_LEVEL_SCHEMA: VolDictType = {
    vol.Required("timer_level"): vol.In(
        ["level1", "level2", "level3", "level4", "holiday", "breeze"]
    ),
    vol.Required("minutes"): cv.positive_int,
}

SET_BREEZE_SCHEMA: VolDictType = {
    vol.Required("breeze_level"): vol.In(["level1", "level2", "level3", "level4"]),
    vol.Required("temperature"): cv.positive_int,
    vol.Required("activate"): bool,
}

SET_POLLUTION_SETTINGS_SCHEMA: VolDictType = {
    vol.Required("day_pollution_level"): vol.In(
        ["level1", "level2", "level3", "level4"]
    ),
    vol.Required("night_pollution_level"): vol.In(
        ["level1", "level2", "level3", "level4"]
    ),
    vol.Optional("humidity_control", default=True): bool,
    vol.Optional("airquality_control", default=True): bool,
    vol.Optional("co2_control", default=True): bool,
    vol.Optional("co2_threshold", default=600): cv.positive_int,
    vol.Optional("co2_hysteresis", default=100): cv.positive_int,
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
        "set_pollution_settings",
        SET_POLLUTION_SETTINGS_SCHEMA,
        "set_pollution_settings",
    )


class RensonFan(RensonEntity, FanEntity):
    """Representation of the Renson fan platform."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

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

        if level == Level.BREEZE.value:
            level = self.api.parse_value(
                self.api.get_field_value(
                    self.coordinator.data, BREEZE_LEVEL_FIELD.name
                ),
                DataType.LEVEL,
            )
        else:
            level = self.api.parse_value(
                self.api.get_field_value(
                    self.coordinator.data, CURRENT_LEVEL_FIELD.name
                ),
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

        level = self.api.parse_value(
            self.api.get_field_value(self.coordinator.data, CURRENT_LEVEL_FIELD.name),
            DataType.LEVEL,
        )

        if percentage == 0:
            cmd = Level.HOLIDAY
        else:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            cmd = CMD_MAPPING[speed]

        if level == Level.BREEZE.value:
            all_data = self.coordinator.data
            breeze_temp = self.api.get_field_value(all_data, BREEZE_TEMPERATURE_FIELD)
            await self.hass.async_add_executor_job(
                self.api.set_breeze, cmd.name, breeze_temp, True
            )
        else:
            await self.hass.async_add_executor_job(self.api.set_manual_level, cmd)

        await self.coordinator.async_request_refresh()

    async def set_timer_level(self, timer_level: str, minutes: int) -> None:
        """Set timer level."""
        level = Level[str(timer_level).upper()]

        await self.hass.async_add_executor_job(self.api.set_timer_level, level, minutes)

    async def set_breeze(
        self, breeze_level: str, temperature: int, activate: bool
    ) -> None:
        """Configure breeze feature."""
        level = Level[str(breeze_level).upper()]

        await self.hass.async_add_executor_job(
            self.api.set_breeze, level, temperature, activate
        )

    async def set_pollution_settings(
        self,
        day_pollution_level: str,
        night_pollution_level: str,
        humidity_control: bool,
        airquality_control: bool,
        co2_control: str,
        co2_threshold: int,
        co2_hysteresis: int,
    ) -> None:
        """Configure pollutions settings."""
        day = Level[str(day_pollution_level).upper()]
        night = Level[str(night_pollution_level).upper()]

        await self.api.set_pollution(
            day,
            night,
            humidity_control,
            airquality_control,
            co2_control,
            co2_threshold,
            co2_hysteresis,
        )
