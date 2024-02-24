"""Moon phase Calendar."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.util import dt as dt_util

from . import get_moon_phases
from .const import (
    DOMAIN,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)

MOON_SUMMARY = {
    STATE_FIRST_QUARTER: "First quarter",
    STATE_FULL_MOON: "Full moon",
    STATE_LAST_QUARTER: "Last quarter",
    STATE_NEW_MOON: "New moon",
    STATE_WANING_CRESCENT: "Waning crescent",
    STATE_WANING_GIBBOUS: "Waning gibbous",
    STATE_WAXING_CRESCENT: "Waxing crescent",
    STATE_WAXING_GIBBOUS: "Waxing gibbous",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Moon phase Calendar config entry."""

    obj_moon_phases = get_moon_phases(
        dt_util.now(), (dt_util.now() + timedelta(days=30))
    )

    async_add_entities(
        [
            MoonCalendarEntity(
                config_entry.title,
                obj_moon_phases,
                config_entry.entry_id,
            )
        ],
        True,
    )


class MoonCalendarEntity(CalendarEntity):
    """Representation of a Moon Phase Calendar element."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "moon_phases"

    def __init__(
        self,
        name: str,
        obj_moon_phases: list[dict[str, Any]],
        unique_id: str,
    ) -> None:
        """Initialize MoonCalendarEntity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
        )
        self._obj_moon_phases = obj_moon_phases

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming moon    phase."""
        summary: str
        for moon_phase in self._obj_moon_phases:
            if moon_phase["date"] >= dt_util.now().date():
                summary = moon_phase["phase"]
                next_moon_phase = (
                    moon_phase["date"],
                    summary,
                    moon_phase["end"],
                )
                break

        return CalendarEvent(
            summary=async_translate_calendar_summary(
                self.hass,
                DOMAIN,
                self._attr_translation_key,
                next_moon_phase[1],
            ),
            start=next_moon_phase[0],
            end=next_moon_phase[2],
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        obj_moon_phases = get_moon_phases(start_date, end_date)

        event_list: list[CalendarEvent] = []

        for moon_phase in obj_moon_phases:
            if (
                end_date is not None
                and start_date.date() <= moon_phase["date"] <= end_date.date()
            ):
                event = CalendarEvent(
                    summary=async_translate_calendar_summary(
                        self.hass,
                        DOMAIN,
                        self._attr_translation_key,
                        moon_phase["phase"],
                    ),
                    start=moon_phase["date"],
                    end=moon_phase["end"],
                )
                event_list.append(event)

        return event_list


def async_translate_calendar_summary(
    hass: HomeAssistant,
    platform: str,
    translation_key: str | None,
    summary: str,
) -> str:
    """Translate provided summary calendar using cached translations for currently selected language."""
    language = hass.config.language
    if translation_key is not None and summary is not None:
        localize_key = f"component.{platform}.entity.calendar.{translation_key}.state_attributes.message.state.{summary}"
        translations = async_get_cached_translations(hass, language, "entity")
        if localize_key in translations:
            return translations[localize_key]
    return summary
