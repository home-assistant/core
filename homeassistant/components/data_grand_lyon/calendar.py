"""Calendar platform for the Data Grand Lyon integration."""

from datetime import datetime
from typing import override

from data_grand_lyon_ha import (
    TclAlert,
    filter_tcl_active_alerts,
    sort_tcl_alerts_by_relevance,
)

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import SUBENTRY_TYPE_LINE, TZ_PARIS
from .coordinator import DataGrandLyonConfigEntry
from .entity import DataGrandLyonLineEntity

PARALLEL_UPDATES = 0

ALERTS_DESCRIPTION = CalendarEntityDescription(
    key="alerts",
    translation_key="alerts",
)


def _tcl_now() -> datetime:
    """Return the current time as a naive Paris datetime, as TCL publishes them."""
    return dt_util.utcnow().astimezone(TZ_PARIS).replace(tzinfo=None)


def _calendar_event(alert: TclAlert) -> CalendarEvent:
    """Convert a TCL alert into a calendar event."""
    # TCL's `n` field is a positional index that changes on every fetch, so no
    # stable event uid can be derived from the data.
    return CalendarEvent(
        start=alert.debut.replace(tzinfo=TZ_PARIS),
        end=alert.fin.replace(tzinfo=TZ_PARIS),
        summary=alert.titre.strip(),
        description=f"{alert.message}\n\nCause: {alert.cause}\nType: {alert.type}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon calendar entities."""
    alerts_coordinator = entry.runtime_data.alerts_coordinator

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LINE):
        async_add_entities(
            [
                DataGrandLyonLineCalendar(
                    alerts_coordinator, subentry, ALERTS_DESCRIPTION
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonLineCalendar(DataGrandLyonLineEntity, CalendarEntity):
    """Calendar of TCL traffic alerts for a line."""

    _attr_name = None

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the most relevant alert that has not ended yet."""
        now = _tcl_now()
        alerts = filter_tcl_active_alerts(self.coordinator.data[self._subentry_id], now)
        if not alerts:
            return None
        return _calendar_event(sort_tcl_alerts_by_relevance(alerts, now)[0])

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the line's alerts overlapping the requested window."""
        window_start = start_date.astimezone(TZ_PARIS).replace(tzinfo=None)
        window_end = end_date.astimezone(TZ_PARIS).replace(tzinfo=None)
        return [
            _calendar_event(alert)
            for alert in self.coordinator.data[self._subentry_id]
            if alert.debut < window_end and alert.fin > window_start
        ]
