"""Common utility functions."""

import datetime
from functools import reduce
from zoneinfo import ZoneInfo


def next_slot(config_entry, data):
    """Get the next charge slot start/end times."""
    slots = slot_list(data)
    collapse_slots = config_entry.options.get("never_collapse_slots", False)

    start = None
    end = None

    # Loop through slots
    for slot in slots:
        # Only take the first slot start/end that matches. These are in order.
        if end is None and slot["end"] > datetime.datetime.now().astimezone():
            end = slot["end"]

        if (
            start is None
            and slot["start"] > datetime.datetime.now().astimezone()
            and slot["start"] != end
        ):
            start = slot["start"]

        if collapse_slots and slot["start"] == end:
            end = slot["end"]

    return {"start": start, "end": end}


def slot_list(data):
    """Get list of charge slots."""
    session_slots = data["allSessionSlots"]
    if session_slots is None or len(session_slots) == 0:
        return []

    slots = []
    wh_tally = 0

    if (
        "batterySocBefore" in data
        and data["batterySocBefore"] is not None
        and data["batterySocBefore"]["wh"] is not None
    ):
        wh_tally = data["batterySocBefore"]["wh"]  # Get the wh value we start from

    for slot in session_slots:
        slots.append(
            {
                "start": datetime.datetime.fromtimestamp(
                    slot["startTimeMs"] / 1000, tz=datetime.UTC
                )
                .replace(tzinfo=ZoneInfo("UTC"), microsecond=0)
                .astimezone(),
                "end": datetime.datetime.fromtimestamp(
                    slot["endTimeMs"] / 1000, tz=datetime.UTC
                )
                .replace(tzinfo=ZoneInfo("UTC"), microsecond=0)
                .astimezone(),
                "charge_in_kwh": -(
                    (slot["estimatedSoc"]["wh"] - wh_tally) / 1000
                ),  # Work out how much we add in just this slot
                "source": "smart-charge",
                "location": None,
            }
        )

        wh_tally = slot["estimatedSoc"]["wh"]

    return slots


def slot_list_str(config_entry, slots):
    """Convert slot list to string."""

    # Convert list to tuples of times
    t_slots = [
        (slot["start"].strftime("%H:%M"), slot["end"].strftime("%H:%M"))
        for slot in slots
    ]

    state = []

    if not config_entry.options.get("never_collapse_slots", False):
        # Collapse slots so consecutive slots become one
        for _i, slot in enumerate(t_slots):
            if not state or state[-1][1] != slot[0]:
                state.append(slot)
            else:
                state[-1] = (state[-1][0], slot[1])
    else:
        state = t_slots

    # Convert list of tuples to string
    state = reduce(lambda acc, slot: acc + f"{slot[0]}-{slot[1]}, ", state, "")[:-2]

    # Make sure we return None/Unknown if the list is empty
    return None if state == "" else state


def in_slot(data):
    """Are we currently in a charge slot."""
    slots = slot_list(data)

    # Loop through slots
    for slot in slots:
        # If we are in one
        if (
            slot["start"] < datetime.datetime.now().astimezone()
            and slot["end"] > datetime.datetime.now().astimezone()
        ):
            return True

    return False


def time_next_occurs(hour, minute):
    """Find when this time next occurs."""
    current = datetime.datetime.now()
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= datetime.datetime.now():
        target = target + datetime.timedelta(days=1)

    return target


def session_in_progress(config_entry, data):
    """Is there a session in progress.

    Used to check if we should update the current session rather than the first schedule.
    """
    # If config option set, never update session specific schedule
    if config_entry.options.get("never_session_specific", False):
        return False

    # Default to False with no data
    if not data:
        return False

    # Car disconnected or pending approval, we should update the schedule
    if data["mode"] == "DISCONNECTED" or data["mode"] == "PENDING_APPROVAL":
        return False

    return True
