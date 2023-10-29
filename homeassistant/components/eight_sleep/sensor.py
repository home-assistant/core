"""Support for Eight Sleep sensors."""
from __future__ import annotations

import logging
from typing import Any

from pyeight.eight import EightSleep
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import EightSleepBaseEntity, EightSleepConfigEntryData
from .const import ATTR_DURATION, ATTR_TARGET, DOMAIN, SERVICE_HEAT_SET

ATTR_ROOM_TEMP = "Room Temperature"
ATTR_AVG_ROOM_TEMP = "Average Room Temperature"
ATTR_BED_TEMP = "Bed Temperature"
ATTR_AVG_BED_TEMP = "Average Bed Temperature"
ATTR_RESP_RATE = "Respiratory Rate"
ATTR_AVG_RESP_RATE = "Average Respiratory Rate"
ATTR_HEART_RATE = "Heart Rate"
ATTR_AVG_HEART_RATE = "Average Heart Rate"
ATTR_SLEEP_DUR = "Time Slept"
ATTR_LIGHT_PERC = f"Light Sleep {PERCENTAGE}"
ATTR_DEEP_PERC = f"Deep Sleep {PERCENTAGE}"
ATTR_REM_PERC = f"REM Sleep {PERCENTAGE}"
ATTR_TNT = "Tosses & Turns"
ATTR_SLEEP_STAGE = "Sleep Stage"
ATTR_TARGET_HEAT = "Target Heating Level"
ATTR_ACTIVE_HEAT = "Heating Active"
ATTR_DURATION_HEAT = "Heating Time Remaining"
ATTR_PROCESSING = "Processing"
ATTR_SESSION_START = "Session Start"
ATTR_FIT_DATE = "Fitness Date"
ATTR_FIT_DURATION_SCORE = "Fitness Duration Score"
ATTR_FIT_ASLEEP_SCORE = "Fitness Asleep Score"
ATTR_FIT_OUT_SCORE = "Fitness Out-of-Bed Score"
ATTR_FIT_WAKEUP_SCORE = "Fitness Wakeup Score"

_LOGGER = logging.getLogger(__name__)

EIGHT_USER_SENSORS = [
    "current_sleep",
    "current_sleep_fitness",
    "last_sleep",
    "bed_temperature",
    "sleep_stage",
]
EIGHT_HEAT_SENSORS = ["bed_state"]
EIGHT_ROOM_SENSORS = ["room_temperature"]

VALID_TARGET_HEAT = vol.All(vol.Coerce(int), vol.Clamp(min=-100, max=100))
VALID_DURATION = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=28800))

SERVICE_EIGHT_SCHEMA = {
    ATTR_TARGET: VALID_TARGET_HEAT,
    ATTR_DURATION: VALID_DURATION,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the eight sleep sensors."""
    config_entry_data: EightSleepConfigEntryData = hass.data[DOMAIN][entry.entry_id]
    eight = config_entry_data.api
    heat_coordinator = config_entry_data.heat_coordinator
    user_coordinator = config_entry_data.user_coordinator

    all_sensors: list[SensorEntity] = []

    for obj in eight.users.values():
        all_sensors.extend(
            EightUserSensor(entry, user_coordinator, eight, obj.user_id, sensor)
            for sensor in EIGHT_USER_SENSORS
        )
        all_sensors.extend(
            EightHeatSensor(entry, heat_coordinator, eight, obj.user_id, sensor)
            for sensor in EIGHT_HEAT_SENSORS
        )

    all_sensors.extend(
        EightRoomSensor(entry, user_coordinator, eight, sensor)
        for sensor in EIGHT_ROOM_SENSORS
    )

    async_add_entities(all_sensors)

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_HEAT_SET,
        SERVICE_EIGHT_SCHEMA,
        "async_heat_set",
    )


class EightHeatSensor(EightSleepBaseEntity, SensorEntity):
    """Representation of an eight sleep heat-based sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        user_id: str,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, coordinator, eight, user_id, sensor)
        assert self._user_obj

        _LOGGER.debug(
            "Heat Sensor: %s, Side: %s, User: %s",
            self._sensor,
            self._user_obj.side,
            self._user_id,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        assert self._user_obj
        return self._user_obj.heating_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attributes."""
        assert self._user_obj
        return {
            ATTR_TARGET_HEAT: self._user_obj.target_heating_level,
            ATTR_ACTIVE_HEAT: self._user_obj.now_heating,
            ATTR_DURATION_HEAT: self._user_obj.heating_remaining,
        }


def _get_breakdown_percent(
    attr: dict[str, Any], key: str, denominator: int | float
) -> int | float:
    """Get a breakdown percent."""
    try:
        return round((attr["breakdown"][key] / denominator) * 100, 2)
    except (ZeroDivisionError, KeyError):
        return 0


def _get_rounded_value(attr: dict[str, Any], key: str) -> int | float | None:
    """Get rounded value for given key."""
    if (val := attr.get(key)) is None:
        return None
    return round(val, 2)


class EightUserSensor(EightSleepBaseEntity, SensorEntity):
    """Representation of an eight sleep user-based sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        user_id: str,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, coordinator, eight, user_id, sensor)
        assert self._user_obj

        if self._sensor == "bed_temperature":
            self._attr_icon = "mdi:thermometer"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif self._sensor in ("current_sleep", "last_sleep", "current_sleep_fitness"):
            self._attr_native_unit_of_measurement = "Score"

        if self._sensor != "sleep_stage":
            self._attr_state_class = SensorStateClass.MEASUREMENT

        _LOGGER.debug(
            "User Sensor: %s, Side: %s, User: %s",
            self._sensor,
            self._user_obj.side,
            self._user_id,
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if not self._user_obj:
            return None

        if "current" in self._sensor:
            if "fitness" in self._sensor:
                return self._user_obj.current_sleep_fitness_score
            return self._user_obj.current_sleep_score

        if "last" in self._sensor:
            return self._user_obj.last_sleep_score

        if self._sensor == "bed_temperature":
            return self._user_obj.current_values["bed_temp"]

        if self._sensor == "sleep_stage":
            return self._user_obj.current_values["stage"]

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device state attributes."""
        attr = None
        if "current" in self._sensor and self._user_obj:
            if "fitness" in self._sensor:
                attr = self._user_obj.current_fitness_values
            else:
                attr = self._user_obj.current_values
        elif "last" in self._sensor and self._user_obj:
            attr = self._user_obj.last_values

        if attr is None:
            # Skip attributes if sensor type doesn't support
            return None

        if "fitness" in self._sensor:
            state_attr = {
                ATTR_FIT_DATE: attr["date"],
                ATTR_FIT_DURATION_SCORE: attr["duration"],
                ATTR_FIT_ASLEEP_SCORE: attr["asleep"],
                ATTR_FIT_OUT_SCORE: attr["out"],
                ATTR_FIT_WAKEUP_SCORE: attr["wakeup"],
            }
            return state_attr

        state_attr = {ATTR_SESSION_START: attr["date"]}
        state_attr[ATTR_TNT] = attr["tnt"]
        state_attr[ATTR_PROCESSING] = attr["processing"]

        if attr.get("breakdown") is not None:
            sleep_time = sum(attr["breakdown"].values()) - attr["breakdown"]["awake"]
            state_attr[ATTR_SLEEP_DUR] = sleep_time
            state_attr[ATTR_LIGHT_PERC] = _get_breakdown_percent(
                attr, "light", sleep_time
            )
            state_attr[ATTR_DEEP_PERC] = _get_breakdown_percent(
                attr, "deep", sleep_time
            )
            state_attr[ATTR_REM_PERC] = _get_breakdown_percent(attr, "rem", sleep_time)

        room_temp = _get_rounded_value(attr, "room_temp")
        bed_temp = _get_rounded_value(attr, "bed_temp")

        if "current" in self._sensor:
            state_attr[ATTR_RESP_RATE] = _get_rounded_value(attr, "resp_rate")
            state_attr[ATTR_HEART_RATE] = _get_rounded_value(attr, "heart_rate")
            state_attr[ATTR_SLEEP_STAGE] = attr["stage"]
            state_attr[ATTR_ROOM_TEMP] = room_temp
            state_attr[ATTR_BED_TEMP] = bed_temp
        elif "last" in self._sensor:
            state_attr[ATTR_AVG_RESP_RATE] = _get_rounded_value(attr, "resp_rate")
            state_attr[ATTR_AVG_HEART_RATE] = _get_rounded_value(attr, "heart_rate")
            state_attr[ATTR_AVG_ROOM_TEMP] = room_temp
            state_attr[ATTR_AVG_BED_TEMP] = bed_temp

        return state_attr


class EightRoomSensor(EightSleepBaseEntity, SensorEntity):
    """Representation of an eight sleep room sensor."""

    _attr_icon = "mdi:thermometer"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        entry,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, coordinator, eight, None, sensor)

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self._eight.room_temperature
