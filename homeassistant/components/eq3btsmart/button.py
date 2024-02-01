"""Platform for eQ-3 button entities."""

from collections.abc import Mapping
import logging
from typing import Any

from eq3btsmart import Thermostat
from eq3btsmart.adapter.eq3_schedule_time import Eq3ScheduleTime
from eq3btsmart.adapter.eq3_temperature import Eq3Temperature
from eq3btsmart.const import WeekDay
from eq3btsmart.models import Schedule, ScheduleDay, ScheduleHour

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry, UndefinedType
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_NAME_FETCH,
    ENTITY_NAME_FETCH_SCHEDULE,
    SERVICE_SET_SCHEDULE,
)
from .eq3_entity import Eq3Entity
from .models import Eq3Config, Eq3ConfigEntry
from .schemas import SCHEMA_SCHEDULE_SET

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Handle config entry setup."""

    eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN][config_entry.entry_id]
    thermostat = eq3_config_entry.thermostat
    eq3_config = eq3_config_entry.eq3_config

    entities_to_add: list[Entity] = [FetchScheduleButton(eq3_config, thermostat)]
    if eq3_config.debug_mode:
        entities_to_add += [
            FetchButton(eq3_config, thermostat),
        ]

    async_add_entities(entities_to_add)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        SCHEMA_SCHEDULE_SET,
        SERVICE_SET_SCHEDULE,
    )


class Base(Eq3Entity, ButtonEntity):
    """Base class for all eQ-3 buttons."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the base class."""

        super().__init__(eq3_config, thermostat)

        self._attr_has_entity_name = True

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID for the entity."""

        if self.name is None or isinstance(self.name, UndefinedType):
            return None

        return format_mac(self._eq3_config.mac_address) + "_" + self.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._eq3_config.mac_address)},
        )


class FetchScheduleButton(Base):
    """Button to fetch the schedule from the thermostat."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the fetch schedule button."""

        super().__init__(eq3_config, thermostat)

        self._thermostat.register_update_callback(self.schedule_update_ha_state)
        self._attr_name = ENTITY_NAME_FETCH_SCHEDULE

    async def async_press(self) -> None:
        """Handle a button press."""

        await self._thermostat.async_get_schedule()

    async def set_schedule(self, **kwargs) -> None:
        """Handle the set schedule service."""

        schedule = Schedule()
        for day in kwargs["days"]:
            index = WEEKDAYS.index(day)
            week_day = WeekDay.from_index(index)

            schedule_hours: list[ScheduleHour] = []
            schedule_day = ScheduleDay(week_day=week_day, schedule_hours=schedule_hours)

            times = [
                kwargs.get(f"next_change_at_{i}", None)
                for i in range(6)
                if f"next_change_at_{i}" in kwargs
            ]
            temps = [kwargs.get(f"target_temp_{i}", None) for i in range(6)]

            times = list(filter(None, times))
            temps = list(filter(None, temps))

            if len(times) != len(temps) - 1:
                raise ServiceValidationError("Times and temps must be of equal length")

            for time, temp in zip(times, temps):
                schedule_hour = ScheduleHour(
                    target_temperature=Eq3Temperature(temp),
                    next_change_at=Eq3ScheduleTime(time),
                )
                schedule_hours.append(schedule_hour)

            schedule.schedule_days.append(schedule_day)

        await self._thermostat.async_set_schedule(schedule=schedule)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""

        schedule = {}
        for day in self._thermostat.schedule.schedule_days:
            schedule[str(day.week_day)] = [
                {
                    "target_temperature": schedule_hour.target_temperature.value,
                    "next_change_at": schedule_hour.next_change_at.value.isoformat(),
                }
                for schedule_hour in day.schedule_hours
            ]

        return {"schedule": schedule}


class FetchButton(Base):
    """Button to fetch the current state from the thermostat."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the fetch button."""

        super().__init__(eq3_config, thermostat)

        self._attr_name = ENTITY_NAME_FETCH
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle a button press."""

        await self._thermostat.async_get_status()
