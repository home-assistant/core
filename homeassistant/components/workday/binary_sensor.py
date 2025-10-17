"""Sensor to indicate whether the current day is a workday."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from holidays import HolidayBase
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)

from . import WorkdayConfigEntry
from .const import CONF_EXCLUDES, CONF_OFFSET, CONF_WORKDAYS
from .entity import BaseWorkdayEntity

SERVICE_CHECK_DATE: Final = "check_date"
CHECK_DATE: Final = "check_date"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkdayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Workday sensor."""
    days_offset: int = int(entry.options[CONF_OFFSET])
    excludes: list[str] = entry.options[CONF_EXCLUDES]
    sensor_name: str = entry.options[CONF_NAME]
    workdays: list[str] = entry.options[CONF_WORKDAYS]
    obj_holidays = entry.runtime_data

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CHECK_DATE,
        {vol.Required(CHECK_DATE): cv.date},
        "check_date",
        None,
        SupportsResponse.ONLY,
    )

    async_add_entities(
        [
            IsWorkdaySensor(
                obj_holidays,
                workdays,
                excludes,
                days_offset,
                sensor_name,
                entry.entry_id,
            )
        ],
    )


class IsWorkdaySensor(BaseWorkdayEntity, BinarySensorEntity):
    """Implementation of a Workday sensor."""

    _attr_name = None

    def __init__(
        self,
        obj_holidays: HolidayBase,
        workdays: list[str],
        excludes: list[str],
        days_offset: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Workday sensor."""
        super().__init__(
            obj_holidays,
            workdays,
            excludes,
            days_offset,
            name,
            entry_id,
        )
        self._attr_extra_state_attributes = {
            CONF_WORKDAYS: workdays,
            CONF_EXCLUDES: excludes,
            CONF_OFFSET: days_offset,
        }

    def update_data(self, now: datetime) -> None:
        """Get date and look whether it is a holiday."""
        self._attr_is_on = self.date_is_workday(now)
