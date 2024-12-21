"""Holiday Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from holidays import PUBLIC, HolidayBase, country_holidays

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import CONF_CATEGORIES, CONF_PROVINCE, DOMAIN


def _get_obj_holidays_and_language(
    country: str,
    province: str | None,
    language: str,
    selected_categories: list[str] | None,
) -> tuple[HolidayBase, str]:
    """Get the object for the requested country and year."""
    if selected_categories is None:
        categories = [PUBLIC]
    else:
        categories = [PUBLIC, *selected_categories]

    obj_holidays = country_holidays(
        country,
        subdiv=province,
        years={dt_util.now().year, dt_util.now().year + 1},
        language=language,
        categories=categories,
    )
    if language == "en":
        for lang in obj_holidays.supported_languages:
            if lang.startswith("en"):
                obj_holidays = country_holidays(
                    country,
                    subdiv=province,
                    years={dt_util.now().year, dt_util.now().year + 1},
                    language=lang,
                    categories=categories,
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
            categories=categories,
        )
        language = default_language

    return (obj_holidays, language)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Holiday Calendar config entry."""
    country: str = config_entry.data[CONF_COUNTRY]
    province: str | None = config_entry.data.get(CONF_PROVINCE)
    categories: list[str] | None = config_entry.options.get(CONF_CATEGORIES)
    language = hass.config.language

    obj_holidays, language = await hass.async_add_executor_job(
        _get_obj_holidays_and_language, country, province, language, categories
    )

    async_add_entities(
        [
            HolidayCalendarEntity(
                config_entry.title,
                country,
                province,
                language,
                categories,
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
    _attr_event: CalendarEvent | None = None
    _attr_should_poll = False
    unsub: CALLBACK_TYPE | None = None

    def __init__(
        self,
        name: str,
        country: str,
        province: str | None,
        language: str,
        categories: list[str] | None,
        obj_holidays: HolidayBase,
        unique_id: str,
    ) -> None:
        """Initialize HolidayCalendarEntity."""
        self._country = country
        self._province = province
        self._location = name
        self._language = language
        self._categories = categories
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
        )
        self._obj_holidays = obj_holidays

    def get_next_interval(self, now: datetime) -> datetime:
        """Compute next time an update should occur."""
        tomorrow = dt_util.as_local(now) + timedelta(days=1)
        return dt_util.start_of_local_day(tomorrow)

    def _update_state_and_setup_listener(self) -> None:
        """Update state and setup listener for next interval."""
        now = dt_util.now()
        self._attr_event = self.update_event(now)
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval(now)
        )

    @callback
    def point_in_time_listener(self, time_date: datetime) -> None:
        """Get the latest data and update state."""
        self._update_state_and_setup_listener()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Set up first update."""
        self._update_state_and_setup_listener()

    def update_event(self, now: datetime) -> CalendarEvent | None:
        """Return the next upcoming event."""
        next_holiday = None
        for holiday_date, holiday_name in sorted(
            self._obj_holidays.items(), key=lambda x: x[0]
        ):
            if holiday_date >= now.date():
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

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._attr_event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        obj_holidays = country_holidays(
            self._country,
            subdiv=self._province,
            years=list({start_date.year, end_date.year}),
            language=self._language,
            categories=self._categories,
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
