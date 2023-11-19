"""Holiday Calendar."""
from __future__ import annotations

from datetime import datetime

from holidays import country_holidays

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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

    async_add_entities(
        [
            HolidayCalendarEntity(
                hass,
                config_entry.title,
                country,
                province,
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
        hass: HomeAssistant,
        name: str,
        country: str,
        province: str | None,
        unique_id: str,
    ) -> None:
        """Initialize HolidayCalendarEntity."""
        self._country = country
        self._province = province
        self._location = name
        self._event: CalendarEvent | None = None
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

        obj_holidays = country_holidays(self._country, subdiv=self._province)
        available_languages = obj_holidays.supported_languages

        if hass.config.language in available_languages:
            self._default_language = hass.config.language
        else:
            self._default_language = obj_holidays.default_language or "en_US"

        if self._default_language == "en" and self._country != "CA":
            self._default_language = "en_US"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        obj_holidays = country_holidays(
            self._country,
            subdiv=self._province,
            years=[dt_util.now().year, dt_util.now().year + 1],
            language=self._default_language,
        )

        next_holiday = min(
            (
                (holiday_date, holiday_name)
                for holiday_date, holiday_name in obj_holidays.items()
                if holiday_date >= dt_util.now().date()
            ),
            key=lambda x: x[0],
        )

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
            language=self._default_language,
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
