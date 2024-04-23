"""Holiday Calendar."""

from __future__ import annotations

from datetime import datetime

from holidays import HolidayBase, country_holidays

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_PROVINCE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Holiday Calendar config entry."""
    country: str = config_entry.data[CONF_COUNTRY]
    province: str | None = config_entry.data.get(CONF_PROVINCE)
    language = hass.config.language

    obj_holidays = country_holidays(
        country,
        subdiv=province,
        years={dt_util.now().year, dt_util.now().year + 1},
        language=language,
    )
    if language == "en":
        for lang in obj_holidays.supported_languages:
            if lang.startswith("en"):
                obj_holidays = country_holidays(
                    country,
                    subdiv=province,
                    years={dt_util.now().year, dt_util.now().year + 1},
                    language=lang,
                )
                language = lang
                break
    if (
        obj_holidays.supported_languages
        and language not in obj_holidays.supported_languages
        and (default_language := obj_holidays.default_language)
    ):
        obj_holidays = country_holidays(
            country,
            subdiv=province,
            years={dt_util.now().year, dt_util.now().year + 1},
            language=default_language,
        )
        language = default_language

    async_add_entities(
        [
            HolidayCalendarEntity(
                config_entry.title,
                country,
                province,
                language,
                obj_holidays,
                config_entry.entry_id,
            )
        ],
        True,
    )


class HolidayCalendarEntity(CalendarEntity):
    """Representation of a Holiday Calendar element."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        name: str,
        country: str,
        province: str | None,
        language: str,
        obj_holidays: HolidayBase,
        unique_id: str,
    ) -> None:
        """Initialize HolidayCalendarEntity."""
        self._country = country
        self._province = province
        self._location = name
        self._language = language
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
        )
        self._obj_holidays = obj_holidays

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        next_holiday = None
        for holiday_date, holiday_name in sorted(
            self._obj_holidays.items(), key=lambda x: x[0]
        ):
            if holiday_date >= dt_util.now().date():
                next_holiday = (holiday_date, holiday_name)
                break

        if next_holiday is None:
            return None

        return CalendarEvent(
            summary=next_holiday[1],
            start=next_holiday[0],
            end=next_holiday[0],
            location=self._location,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        obj_holidays = country_holidays(
            self._country,
            subdiv=self._province,
            years=list({start_date.year, end_date.year}),
            language=self._language,
        )

        event_list: list[CalendarEvent] = []

        for holiday_date, holiday_name in obj_holidays.items():
            if start_date.date() <= holiday_date <= end_date.date():
                event = CalendarEvent(
                    summary=holiday_name,
                    start=holiday_date,
                    end=holiday_date,
                    location=self._location,
                )
                event_list.append(event)

        return event_list
