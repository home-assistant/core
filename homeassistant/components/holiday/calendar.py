"""Holiday Calendar."""
from __future__ import annotations

from datetime import date, datetime

from holidays import country_holidays

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PROVINCE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Holiday Calendar config entry."""
    name: str = config_entry.data[CONF_NAME]
    country: str = config_entry.data[CONF_COUNTRY]
    province: str | None = config_entry.data.get(CONF_PROVINCE)

    entity = HolidayCalendarEntity(
        name, country, province, unique_id=config_entry.entry_id
    )
    async_add_entities([entity], True)


class HolidayCalendarEntity(CalendarEntity):
    """Representation of a Holiday Calendar element."""

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str | None,
        country: str | None,
        province: str | None,
        unique_id: str,
    ) -> None:
        """Initialize HolidayCalendarEntity."""
        self._country = country
        self._province = province
        self._event: CalendarEvent | None = None
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the device state attributes."""
        return {
            "location": f"{self._country}, {self._province}"
            if self._province is not None
            else self._country
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if self._country is not None:
            obj_holidays = country_holidays(
                self._country,
                subdiv=self._province,
                years=date.today().year,
                language=self.hass.config.language,
            )

            next_holiday = min(
                (
                    (holiday_date, holiday_name)
                    for holiday_date, holiday_name in obj_holidays.items()
                    if holiday_date >= date.today()
                ),
                key=lambda x: x[0],
            )

            self._event = CalendarEvent(
                summary=next_holiday[1],
                start=next_holiday[0],
                end=next_holiday[0],
            )

            return self._event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        if self._country is not None:
            obj_holidays = country_holidays(
                self._country,
                subdiv=self._province,
                years=list({start_date.year, end_date.year}),
                language=hass.config.language,
            )

            event_list: list[CalendarEvent] = []

            for holiday_date, holiday_name in obj_holidays.items():
                event = CalendarEvent(
                    summary=holiday_name,
                    start=holiday_date,
                    end=holiday_date,
                )
                event_list.append(event)

            return event_list
        return []
