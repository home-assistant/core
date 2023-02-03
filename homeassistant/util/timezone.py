"""Module to get multiple timezones."""
from datetime import datetime

import pytz


def get_multiple_zones_time(zones: str) -> str:
    """Return the current utc and hour of multiple zones."""
    times = ""
    i = 0
    while i < len(zones):
        if zones[i] is not None or zones[i] != "":
            times += zones[i] + " - " + get_locality_time_and_utc(zones[i]) + "\n"

        i += 1

    return times


def get_locality_time_and_utc(zone: str) -> str:
    """Return the current utc and hour of a specific zone."""
    utc = str(get_utc(zone))
    zone_time = datetime.now(pytz.timezone(zone)).strftime("%H:%M:%S")

    if int(utc) >= 0:
        return str("Time: " + zone_time + " UTC+" + utc)

    return str("Time: " + zone_time + " UTC" + utc)


def get_utc(zone: str) -> int:
    """Return the utc of a zone."""
    utc_0_hour = datetime.now().strftime("%H")
    zone_hour = datetime.now(pytz.timezone(zone)).strftime("%H")
    zone_utc = int(utc_0_hour) - int(zone_hour)
    zone_utc *= -1
    return zone_utc
