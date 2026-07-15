"""Write operations for CalDAV events.

Home Assistant addresses an occurrence of a recurring event by the UID of the
series plus a RECURRENCE-ID, and scopes a change to that occurrence alone or to
that occurrence and everything after it. CalDAV has no such call: the whole
series lives in a single calendar object that has to be rewritten by hand.

A single occurrence is dropped with an EXDATE and changed through an overriding
VEVENT carrying a RECURRENCE-ID. "This and future" caps the RRULE with UNTIL.
RFC 5545 requires EXDATE and RECURRENCE-ID to use the value type of DTSTART,
and UNTIL to be UTC whenever DTSTART is a datetime.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import caldav
from icalendar import Event as ICalEvent, vDDDTypes, vRecur

from homeassistant.util import dt as dt_util


def update_event(
    calendar: caldav.Calendar,
    uid: str,
    data: dict[str, Any],
    recurrence_id: str | None = None,
    this_and_future: bool = False,
) -> None:
    """Update a whole series, a single occurrence, or an occurrence onwards."""
    dav_event = calendar.event_by_uid(uid)
    ical = dav_event.icalendar_instance
    master = _master(ical)

    if recurrence_id is None:
        _apply(master, data)
        _save(dav_event, ical, master)
        return

    occurrence = parse_recurrence_id(recurrence_id)

    if not this_and_future:
        target = _override(ical, occurrence) or _new_override(ical, master, occurrence)
        _apply(target, data)
        _save(dav_event, ical, target)
        return

    if _utc(occurrence) <= _utc(master["DTSTART"].dt):
        _apply(master, data)
        _save(dav_event, ical, master)
        return

    # RFC 4791 allows only one UID per object, so the tail needs its own.
    tail = dict(data)
    if tail.get("rrule") is None:
        tail.pop("rrule", None)

    _cap_series(master, occurrence)
    _drop_overrides(ical, occurrence, from_occurrence=True)
    _save(dav_event, ical, master)
    calendar.add_event(**tail)


def delete_event(
    calendar: caldav.Calendar,
    uid: str,
    recurrence_id: str | None = None,
    this_and_future: bool = False,
) -> None:
    """Delete a whole series, a single occurrence, or an occurrence onwards."""
    dav_event = calendar.event_by_uid(uid)

    if recurrence_id is None:
        dav_event.delete()
        return

    ical = dav_event.icalendar_instance
    master = _master(ical)
    occurrence = parse_recurrence_id(recurrence_id)

    if this_and_future:
        # Capping before the first occurrence would leave an empty series.
        if _utc(occurrence) <= _utc(master["DTSTART"].dt):
            dav_event.delete()
            return
        _cap_series(master, occurrence)
        _drop_overrides(ical, occurrence, from_occurrence=True)
    else:
        _add_exdate(master, occurrence)
        _drop_overrides(ical, occurrence, from_occurrence=False)

    _save(dav_event, ical, master)


def parse_recurrence_id(value: str) -> datetime | date:
    """Parse the recurrence id Home Assistant echoes back.

    Dates are tried first: parse_datetime also accepts a date-only string and
    would turn an all day occurrence into midnight, losing the value type that
    EXDATE and UNTIL have to match.
    """
    parsed = dt_util.parse_date(value) or dt_util.parse_datetime(value)
    if parsed is None:
        raise ValueError(f"Unable to parse recurrence id: {value}")
    return parsed


def _utc(value: datetime | date) -> datetime:
    """Normalize dates and floating times so comparisons never mix types."""
    if not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return value.astimezone(UTC)


def _master(ical: Any) -> Any:
    vevents = list(ical.walk("VEVENT"))
    if not vevents:
        raise ValueError("Calendar object contains no event")
    for vevent in vevents:
        if "RECURRENCE-ID" not in vevent:
            return vevent
    return vevents[0]


def _overrides(ical: Any) -> list[Any]:
    return [vevent for vevent in ical.walk("VEVENT") if "RECURRENCE-ID" in vevent]


def _override(ical: Any, occurrence: datetime | date) -> Any | None:
    target = _utc(occurrence)
    for vevent in _overrides(ical):
        if _utc(vevent["RECURRENCE-ID"].dt) == target:
            return vevent
    return None


def _new_override(ical: Any, master: Any, occurrence: datetime | date) -> Any:
    override = ICalEvent()
    override.add("UID", str(master["UID"]))
    override.add("DTSTAMP", dt_util.utcnow())
    override.add("RECURRENCE-ID", vDDDTypes(_match_type(master, occurrence)))
    ical.add_component(override)
    return override


def _drop_overrides(
    ical: Any, occurrence: datetime | date, from_occurrence: bool
) -> None:
    target = _utc(occurrence)
    for vevent in _overrides(ical):
        moment = _utc(vevent["RECURRENCE-ID"].dt)
        if moment >= target if from_occurrence else moment == target:
            ical.subcomponents.remove(vevent)


def _match_type(master: Any, occurrence: datetime | date) -> datetime | date:
    """Return the occurrence in the value type the master DTSTART uses."""
    if isinstance(master["DTSTART"].dt, datetime):
        return _utc(occurrence)
    return occurrence.date() if isinstance(occurrence, datetime) else occurrence


def _add_exdate(master: Any, occurrence: datetime | date) -> None:
    master.add("EXDATE", vDDDTypes(_match_type(master, occurrence)))


def _cap_series(master: Any, occurrence: datetime | date) -> None:
    rrule = master.get("RRULE")
    if rrule is None:
        raise ValueError("Event is not a recurring series")
    recur = vRecur(dict(rrule))
    recur.pop("COUNT", None)
    recur["UNTIL"] = [_until(master, occurrence)]
    _replace(master, "rrule", recur)


def _until(master: Any, occurrence: datetime | date) -> datetime | date:
    """Return an UNTIL that stops the series before the occurrence."""
    if isinstance(master["DTSTART"].dt, datetime):
        return _utc(occurrence) - timedelta(seconds=1)
    day = occurrence.date() if isinstance(occurrence, datetime) else occurrence
    return day - timedelta(days=1)


def _apply(component: Any, data: dict[str, Any]) -> None:
    _replace(component, "summary", data.get("summary"))
    if "dtstart" in data:
        _replace(component, "dtstart", data["dtstart"])
    if "dtend" in data:
        # RFC 5545 forbids DURATION alongside DTEND.
        _replace(component, "duration", None)
        _replace(component, "dtend", data["dtend"])
    _replace(component, "description", data.get("description"))
    _replace(component, "location", data.get("location"))
    if "rrule" in data:
        _replace(
            component,
            "rrule",
            vRecur.from_ical(data["rrule"]) if data["rrule"] else None,
        )


def _save(dav_event: caldav.CalendarObjectResource, ical: Any, touched: Any) -> None:
    _replace(touched, "last-modified", dt_util.utcnow())
    _replace(touched, "sequence", int(touched.get("sequence", 0)) + 1)
    dav_event.data = ical.to_ical().decode("utf-8")
    # Defaults would bump SEQUENCE twice and, when an override comes first,
    # merge back only that component, dropping the edits to the master.
    # caldav.CalendarObjectResource types against a shim that predates
    # only_this_recurrence; the runtime class accepts it.
    dav_event.save(increase_seqno=False, only_this_recurrence=False)  # type: ignore[call-arg]


def _replace(component: Any, key: str, value: Any) -> None:
    if key in component:
        del component[key]
    if value is not None:
        component.add(key, value)
