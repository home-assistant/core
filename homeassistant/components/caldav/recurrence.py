"""Write operations for CalDAV events.

Home Assistant addresses an occurrence of a recurring event by the UID of the
series plus a RECURRENCE-ID, and scopes a change to that occurrence alone or to
that occurrence and everything after it. CalDAV has no such call: the whole
series lives in a single calendar object that has to be rewritten by hand.

A single occurrence is dropped with an EXDATE and changed through an overriding
VEVENT carrying a RECURRENCE-ID. "This and future" caps the RRULE with UNTIL
and drops later RDATEs; an update clones the resource into a second object
holding the remaining occurrences. RFC 5545 requires EXDATE, RECURRENCE-ID and
UNTIL to follow DTSTART: its value type, and its zone or lack of one. A
floating DTSTART keeps them floating; a zoned one puts them in UTC.
"""

from datetime import UTC, date, datetime, time, timedelta
import logging
from typing import Any

import caldav
from caldav.lib.error import DAVError
from dateutil.rrule import rrulestr
from icalendar import (
    Calendar as ICalCalendar,
    Event as ICalEvent,
    vDDDLists,
    vDDDTypes,
    vRecur,
)
import requests

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

_WRITE_FAILURES = (requests.ConnectionError, requests.Timeout, DAVError, ValueError)


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
        old_start = _utc(master["DTSTART"].dt)
        _apply(master, data)
        # A new rule or start invalidates the RECURRENCE-IDs of overrides.
        if data.get("rrule") or _utc(master["DTSTART"].dt) != old_start:
            _drop_overrides(
                ical, master, old_start, from_occurrence=False, all_overrides=True
            )
        _save(dav_event, ical, master)
        return

    occurrence = parse_recurrence_id(recurrence_id)

    if not this_and_future:
        target = _override(ical, occurrence) or _new_override(ical, master, occurrence)
        _apply(target, {**data, "rrule": None})
        _save(dav_event, ical, target)
        return

    if _utc(occurrence) <= _utc(master["DTSTART"].dt):
        _apply(master, data)
        _drop_overrides(ical, master, occurrence, from_occurrence=True)
        _save(dav_event, ical, master)
        return

    if "RRULE" not in master and "RDATE" not in master:
        raise ValueError("Event is not a recurring series")

    # A replayed command finds the head already capped and must not clone it
    # over the valid tail.
    if not _has_occurrences_from(master, occurrence):
        return

    # RFC 4791 allows one UID per object; a derived UID makes retries
    # overwrite the tail instead of adding another one.
    tail = calendar.save_event(_tail_ics(ical, master, data, occurrence))
    try:
        _cap_series(master, occurrence)
        _drop_overrides(ical, master, occurrence, from_occurrence=True)
        _save(dav_event, ical, master)
    except _WRITE_FAILURES:
        # A timeout may hit after the server committed the capped head;
        # deleting the tail then would drop every future occurrence.
        if _head_uncapped(calendar, uid, occurrence):
            _discard(tail)
        else:
            _LOGGER.warning(
                "Keeping the split-off series; the head state could not be"
                " verified after a failed update"
            )
        raise


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
        _drop_overrides(ical, master, occurrence, from_occurrence=True)
    else:
        _add_exdate(master, occurrence)
        _drop_overrides(ical, master, occurrence, from_occurrence=False)

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
    override = ICalEvent.from_ical(master.to_ical())
    for key in ("RRULE", "RDATE", "EXDATE"):
        if key in override:
            del override[key]
    _replace(override, "dtstamp", dt_util.utcnow())
    _replace(override, "sequence", None)
    override.add("RECURRENCE-ID", vDDDTypes(_align(master, occurrence)))
    ical.add_component(override)
    return override


def _drop_overrides(
    ical: Any,
    master: Any,
    occurrence: datetime | date,
    from_occurrence: bool,
    all_overrides: bool = False,
) -> None:
    """Remove overrides, but never the component _master() returned.

    On an orphan-override object every VEVENT carries a RECURRENCE-ID and the
    first doubles as the master; removing it would save an empty resource.
    """
    target = _utc(occurrence)
    for vevent in _overrides(ical):
        if vevent is master:
            continue
        moment = _utc(vevent["RECURRENCE-ID"].dt)
        if all_overrides or (moment >= target if from_occurrence else moment == target):
            ical.subcomponents.remove(vevent)


def _align(master: Any, occurrence: datetime | date) -> datetime | date:
    """Return the occurrence in the value type and zone the master DTSTART uses."""
    dtstart = master["DTSTART"].dt
    if not isinstance(dtstart, datetime):
        return occurrence.date() if isinstance(occurrence, datetime) else occurrence
    if not isinstance(occurrence, datetime):
        occurrence = datetime.combine(occurrence, time.min)
    if dtstart.tzinfo is None:
        return occurrence.replace(tzinfo=None)
    return _utc(occurrence)


def _add_exdate(master: Any, occurrence: datetime | date) -> None:
    master.add("EXDATE", vDDDTypes(_align(master, occurrence)))


def _tail_ics(
    ical: Any, master: Any, data: dict[str, Any], occurrence: datetime | date
) -> str:
    """Return the occurrences from the split onwards as their own object."""
    tail = ICalCalendar.from_ical(ical.to_ical())
    vevent = _master(tail)
    for override in _overrides(tail):
        if override is not vevent:
            tail.subcomponents.remove(override)
    _replace(vevent, "uid", _tail_uid(str(master["UID"]), occurrence))
    _replace(vevent, "dtstamp", dt_util.utcnow())
    _replace(vevent, "sequence", None)
    _apply(vevent, data)
    if "rrule" not in data:
        _replace(vevent, "rrule", _tail_rrule(master, occurrence))
    _keep_dates(vevent, "RDATE", occurrence, before=False)
    _keep_dates(vevent, "EXDATE", occurrence, before=False)
    return tail.to_ical().decode("utf-8")


def _tail_uid(uid: str, occurrence: datetime | date) -> str:
    return f"{uid}-{_utc(occurrence).strftime('%Y%m%dT%H%M%SZ')}"


def _tail_rrule(master: Any, occurrence: datetime | date) -> vRecur | None:
    """Return the master's rule with COUNT reduced by the capped head."""
    rrule = master.get("RRULE")
    if rrule is None or _ends_before(master, occurrence):
        return None
    recur = vRecur(dict(rrule))
    if count := recur.get("COUNT"):
        recur["COUNT"] = [count[0] - _occurrences_before(master, occurrence)]
    return recur


def _occurrences_before(master: Any, occurrence: datetime | date) -> int:
    dtstart = master["DTSTART"].dt
    target = _align(master, occurrence)
    if not isinstance(dtstart, datetime):
        dtstart = datetime.combine(dtstart, time.min)
        target = datetime.combine(target, time.min)
    rule = rrulestr(master["RRULE"].to_ical().decode("utf-8"), dtstart=dtstart)
    return sum(1 for moment in rule if moment < target)


def _ends_before(master: Any, occurrence: datetime | date) -> bool:
    """Return whether the rule's own occurrences all lie before the cutoff."""
    recur = master["RRULE"]
    if until := recur.get("UNTIL"):
        return _utc(until[0]) < _utc(_align(master, occurrence))
    if count := recur.get("COUNT"):
        return _occurrences_before(master, occurrence) >= count[0]
    return False


def _has_occurrences_from(master: Any, occurrence: datetime | date) -> bool:
    if master.get("RRULE") is not None and not _ends_before(master, occurrence):
        return True
    return _has_dates_from(master, "RDATE", occurrence)


def _has_dates_from(component: Any, key: str, occurrence: datetime | date) -> bool:
    if key not in component:
        return False
    entries = component[key]
    if not isinstance(entries, list):
        entries = [entries]
    target = _utc(occurrence)
    return any(
        _utc(_start_of(item.dt)) >= target for entry in entries for item in entry.dts
    )


def _head_uncapped(
    calendar: caldav.Calendar, uid: str, occurrence: datetime | date
) -> bool:
    """Return whether the head still holds occurrences from the cutoff on."""
    try:
        ical = calendar.event_by_uid(uid).icalendar_instance
    except requests.ConnectionError, requests.Timeout, DAVError:
        return False
    return _has_occurrences_from(_master(ical), occurrence)


def _discard(tail: Any) -> None:
    try:
        tail.delete()
    except (requests.ConnectionError, requests.Timeout, DAVError) as err:
        _LOGGER.warning(
            "The split-off series could not be removed after a failed update"
            " and may show duplicate events until the update is retried: %s",
            err,
        )


def _cap_series(master: Any, occurrence: datetime | date) -> None:
    rrule = master.get("RRULE")
    if rrule is None and "RDATE" not in master:
        raise ValueError("Event is not a recurring series")
    # A rule that already ends before the cutoff must stay as it is; an UNTIL
    # at the cutoff would add occurrences instead of removing them.
    if rrule is not None and not _ends_before(master, occurrence):
        recur = vRecur(dict(rrule))
        recur.pop("COUNT", None)
        recur["UNTIL"] = [_until(master, occurrence)]
        _replace(master, "rrule", recur)
    _keep_dates(master, "RDATE", occurrence, before=True)
    _keep_dates(master, "EXDATE", occurrence, before=True)


def _keep_dates(
    component: Any, key: str, occurrence: datetime | date, before: bool
) -> None:
    """Keep the RDATE or EXDATE values on one side of the occurrence.

    Property lines are filtered one by one: merging them would force every
    value under a single TZID and shift the instants of the others.
    """
    if key not in component:
        return
    entries = component[key]
    if not isinstance(entries, list):
        entries = [entries]
    target = _utc(occurrence)
    kept_entries = []
    for entry in entries:
        kept = [
            item.dt
            for item in entry.dts
            if (_utc(_start_of(item.dt)) < target) == before
        ]
        if len(kept) == len(entry.dts):
            kept_entries.append(entry)
        elif kept:
            rebuilt = vDDDLists(kept)
            rebuilt.params = entry.params
            kept_entries.append(rebuilt)
    del component[key]
    if kept_entries:
        component[key] = kept_entries if len(kept_entries) > 1 else kept_entries[0]


def _start_of(value: Any) -> datetime | date:
    """Return the start of an RDATE value, which may be a period."""
    return value[0] if isinstance(value, tuple) else value


def _until(master: Any, occurrence: datetime | date) -> datetime | date:
    """Return an UNTIL that stops the series before the occurrence."""
    aligned = _align(master, occurrence)
    if isinstance(aligned, datetime):
        return aligned - timedelta(seconds=1)
    return aligned - timedelta(days=1)


def _apply(component: Any, data: dict[str, Any]) -> None:
    _replace(component, "summary", data.get("summary"))
    if "dtstart" in data:
        _set_time(component, "dtstart", data["dtstart"])
    if "dtend" in data:
        # RFC 5545 forbids DURATION alongside DTEND.
        _replace(component, "duration", None)
        _set_time(component, "dtend", data["dtend"])
    _replace(component, "description", data.get("description"))
    _replace(component, "location", data.get("location"))
    # The frontend never sees the rule (expand strips RRULE), so an absent
    # rrule must not remove the recurrence.
    if rrule := data.get("rrule"):
        _replace(component, "rrule", vRecur.from_ical(rrule))


def _set_time(component: Any, key: str, value: Any) -> None:
    """Write a time in the anchor the component already uses.

    Home Assistant normalizes times to its own zone; writing them as received
    would re-anchor a UTC, TZID or floating series on a summary-only edit and
    shift future occurrences across DST boundaries.
    """
    old = component[key].dt if key in component else None
    if (
        old is not None
        and isinstance(old, datetime) != isinstance(value, datetime)
        and any(k in component for k in ("RRULE", "RDATE", "RECURRENCE-ID"))
    ):
        # UNTIL, RDATE, EXDATE and RECURRENCE-ID would keep the old value type.
        raise ValueError("Cannot change a recurring event between all-day and timed")
    if isinstance(old, datetime) and isinstance(value, datetime):
        if _utc(old) == _utc(value):
            return
        if old.tzinfo is None:
            value = dt_util.as_local(value).replace(tzinfo=None)
        else:
            value = value.astimezone(old.tzinfo)
    _replace(component, key, value)


def _save(dav_event: caldav.CalendarObjectResource, ical: Any, touched: Any) -> None:
    _replace(touched, "last-modified", dt_util.utcnow())
    _replace(touched, "sequence", int(touched.get("sequence", 0)) + 1)
    dav_event.data = ical.to_ical().decode("utf-8")
    # Defaults would bump SEQUENCE twice and merge back only the first
    # component; the ignore covers a legacy shim without only_this_recurrence.
    dav_event.save(increase_seqno=False, only_this_recurrence=False)  # type: ignore[call-arg]


def _replace(component: Any, key: str, value: Any) -> None:
    if key in component:
        del component[key]
    if value is not None:
        component.add(key, value)
