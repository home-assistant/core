"""Module provides utility functions for reading and writing mosque data files.

Used in the Home Assistant Mawaqit integration.
"""

from datetime import datetime, timedelta
import logging
import os

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
import homeassistant.util.dt as dt_util

from .const import CONF_UUID, PRAYER_NAMES, PRAYER_NAMES_IQAMA

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

_LOGGER = logging.getLogger(__name__)


def parse_mosque_data(dict_mosques):
    """Parse mosque data and return names, UUIDs, and calculation methods.

    Args:
        dict_mosques (dict): The mosque data to parse.

    Returns:
        tuple: Parsed mosque data as a tuple of names, UUIDs, and calculation methods,
                        or raw data if raw is True.

    """

    name_servers = []
    uuid_servers = []
    CALC_METHODS = []

    if dict_mosques is not None:
        for mosque in dict_mosques:
            proximity_str = ""
            if "proximity" in mosque:
                distance = mosque["proximity"]
                distance = distance / 1000
                distance = round(distance, 2)
                proximity_str = " (" + str(distance) + "km)"
            name_servers.extend([mosque["label"] + proximity_str])
            uuid_servers.extend([mosque["uuid"]])
            CALC_METHODS.extend([mosque["label"]])

    return name_servers, uuid_servers, CALC_METHODS


def async_save_mosque(
    UUID,
    mosques,
    mawaqit_token=None,
    lat=None,
    longi=None,
) -> tuple[str, dict]:
    """Create a data entry to simplify the process of saving mosque data.

    Args:
        UUID (str): The unique identifier of the mosque.
        mosques (list): List of mosque data dictionaries.
        mawaqit_token (str, optional): Token for Mawaqit API authentication.
        lat (float, optional): Latitude of the mosque.
        longi (float, optional): Longitude of the mosque.

    Returns:
        tuple[str, dict]: A tuple containing the title and data entry dictionary.

    """

    if mawaqit_token is None:
        _LOGGER.error("Token should not be None !")
        raise ValueError("Token should not be None !")

    name_servers, uuid_servers, CALC_METHODS = parse_mosque_data(mosques)
    raw_all_mosques_data = mosques

    mosque = UUID
    index = name_servers.index(mosque)
    mosque_id = uuid_servers[index]

    title = "MAWAQIT" + " - " + raw_all_mosques_data[index]["name"]
    data_entry = {
        CONF_API_KEY: mawaqit_token,
        CONF_UUID: mosque_id,
    }
    if lat is not None and longi is not None:
        data_entry[CONF_LATITUDE] = lat
        data_entry[CONF_LONGITUDE] = longi

    return title, data_entry


def extract_time_from_calendar(
    calendar, prayer_name, target_date, timezone, mode_iqama=False
) -> str | None:
    """Extract the time of a specific prayer for a given date and apply the correct timezone.

    :param calendar: List containing 12 dictionaries (one for each month).
    :param prayer_name: The name of the prayer to extract (e.g., "Fajr", "Dhuhr").
    :param target_date: The date for which to extract the prayer time (datetime.date object).
    :param timezone: The timezone string (e.g., "Europe/Paris") from prayer data.
    :return: The prayer time as a string , or None if missing.
    """

    prayer_name = prayer_name.lower()
    try:
        mode_prayer_name = PRAYER_NAMES_IQAMA if mode_iqama else PRAYER_NAMES

        # Validate prayer name
        if prayer_name.lower() not in mode_prayer_name:
            _LOGGER.error("Invalid prayer name: %s", prayer_name)
            return None

        # Extract month and day from the target_date
        target_month = target_date.month  # Extract month (1-12)
        target_day = str(target_date.day)  # Extract day as a string

        # Validate month data
        if target_month - 1 >= len(calendar):
            _LOGGER.error("Calendar data for month %s is missing", target_month)
            return None

        month_data = calendar[target_month - 1]  # Convert month to 0-based index

        # Get the prayer times for the given day
        target_prayer_times = month_data.get(target_day)

        if not target_prayer_times or len(target_prayer_times) != len(mode_prayer_name):
            _LOGGER.error(
                "Incomplete or missing prayer times for %s-%s", target_month, target_day
            )
            return None

        # Get the index of the requested prayer
        prayer_index = mode_prayer_name.index(prayer_name)

        return target_prayer_times[prayer_index]  # represents the prayer time

    except KeyError as e:
        _LOGGER.error(
            "Key error extracting prayer time for %s on %s: %s",
            prayer_name,
            target_date,
            e,
        )
        return None
    except ValueError as e:
        _LOGGER.error(
            "Value error extracting prayer time for %s on %s: %s",
            prayer_name,
            target_date,
            e,
        )
        return None
    except IndexError as e:
        _LOGGER.error(
            "Index error extracting prayer time for %s on %s: %s",
            prayer_name,
            target_date,
            e,
        )
        return None


def time_with_timezone(timezone, date, time) -> datetime | None:
    """Convert a naive datetime to a timezone-aware datetime.

    Args:
        timezone (str): The timezone string (e.g., "Europe/Paris").
        date (str): The date string in "YYYY-MM-DD" format.
        time (str): The time string in "HH:MM" format.

    Returns:
        datetime: The timezone-aware datetime object, or None if the timezone is invalid.

    """
    tz = dt_util.get_time_zone(timezone)
    if not tz:
        _LOGGER.error("Invalid timezone: %s", timezone)
        return None
    naive_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    return dt_util.as_local(naive_time.replace(tzinfo=tz))


def add_minutes_to_time(time_str, minutes_str):
    """Add minutes to a time string (HH:MM) based on a string input like "+xx".

    :param time_str: Time in "HH:MM" format (e.g., "06:49").
    :param minutes_str: String representing minutes to add (e.g., "+15").
    :return: New time as a string in "HH:MM" format.
    """
    if time_str is None or minutes_str is None:
        raise ValueError("Both time_str and minutes_str must be provided")
    # Parse the base time
    base_time = datetime.strptime(time_str, "%H:%M")

    # Extract minutes from the input string
    if not minutes_str.startswith("+") or not minutes_str[1:].isdigit():
        raise ValueError("Invalid minutes format, expected '+xx'")

    try:
        minutes_to_add = int(minutes_str[1:])  # Extract the integer part

        # Add minutes
        new_time = base_time + timedelta(minutes=minutes_to_add)

        # Format back to string
        return new_time.strftime("%H:%M")

    except (ValueError, TypeError) as e:
        _LOGGER.error("Error in add_minutes_to_time: %s", e)
        return None


def get_next_friday():
    """Return the date of the next Friday after today.

    This function always returns the Friday of the following week if today is Friday,
    i.e., it never returns today's date. If today is any other day, it returns the upcoming Friday.

    :return: A datetime.date object representing the next Friday (never today).
    """
    today = datetime.today().date()
    days_until_friday = (
        4 - today.weekday()
    ) % 7  # 4 represents Friday (Monday=0, ..., Sunday=6)

    if days_until_friday == 0:  # If today is Friday, move to next week
        days_until_friday = 7

    return today + timedelta(days=days_until_friday)  # represents the next Friday


def get_prayer_times_for_two_days(prayer_calendar, today, timezone):
    """Extract prayer times for today and tomorrow from the provided calendar.

    Args:
        prayer_calendar (dict): The yearly prayer times calendar.
        today (datetime): The datetime object representing 'today', not timezone-aware.
        timezone (str): String representing the timezone, e.g., 'Europe/Paris'.

    Returns:
        dict: A dictionary containing prayer times for today and tomorrow.

    """
    tz = dt_util.get_time_zone(timezone)
    today = dt_util.as_local(today.replace(tzinfo=tz))
    tomorrow = today + timedelta(days=1)

    # Extracting times for today and tomorrow
    today_times = prayer_calendar[today.month - 1].get(str(today.day), [])
    tomorrow_times = prayer_calendar[today.month - 1].get(str(tomorrow.day), [])

    return {
        "today": {"date": today.strftime("%Y-%m-%d"), "prayer_times": today_times},
        "tomorrow": {
            "date": tomorrow.strftime("%Y-%m-%d"),
            "prayer_times": tomorrow_times,
        },
    }


def find_next_prayer(current_time, prayer_calendar, timezone):
    """Find the next prayer name and its exact time based on the provided calendar.

    Args:
        current_time (datetime): The current time, expected to be timezone-aware.
        prayer_calendar (dict): The yearly prayer times calendar.
        timezone (str): String representing the timezone, e.g., 'Europe/Paris'.

    Returns:
        tuple: (Next prayer index, Next prayer datetime (timezone-aware))

    """

    # Ensure current time is timezone aware
    tz = dt_util.get_time_zone(timezone)
    if not tz:
        _LOGGER.error("Invalid timezone: %s", timezone)
        return None, None

    current_time = dt_util.as_local(current_time.replace(tzinfo=tz))

    # Get prayer times for today and tomorrow
    prayer_times_two_days = get_prayer_times_for_two_days(
        prayer_calendar, current_time, timezone
    )
    today_prayer_times = prayer_times_two_days["today"]["prayer_times"]
    tomorrow_prayer_times = prayer_times_two_days["tomorrow"]["prayer_times"]

    # Find the next prayer time
    next_prayer_index = None
    next_prayer_datetime = None

    # Check today's remaining prayer times
    for index, time_str in enumerate(today_prayer_times):
        prayer_time = datetime.strptime(time_str, "%H:%M").time()
        prayer_datetime = datetime.combine(current_time.date(), prayer_time, tz)

        if prayer_datetime > current_time:
            next_prayer_index = index
            next_prayer_datetime = prayer_datetime
            break  # Stop at the first future prayer time

    # If no prayer is found today, use the first prayer time tomorrow
    if next_prayer_index is None and tomorrow_prayer_times:
        next_prayer_index = 0
        prayer_time = datetime.strptime(tomorrow_prayer_times[0], "%H:%M").time()
        next_prayer_datetime = datetime.combine(
            current_time.date() + timedelta(days=1), prayer_time, tz
        )

    return next_prayer_index, next_prayer_datetime


def get_regular_prayer_time(prayer_data: dict, prayer_name: str) -> datetime | None:
    """Get regular prayer time (Fajr, Dhuhr, Asr, Maghrib, Isha)."""
    calendar = prayer_data.get("calendar")
    timezone = prayer_data.get("timezone")

    if not calendar or not timezone:
        _LOGGER.warning("Missing calendar or timezone data for %s", prayer_name)
        return None

    # Get today's date
    day = dt_util.now().date()
    prayer_time = extract_time_from_calendar(calendar, prayer_name, day, timezone)

    if not prayer_time:
        return None

    localized_prayer_time = time_with_timezone(timezone, day, prayer_time)
    if localized_prayer_time:
        return localized_prayer_time.astimezone(dt_util.UTC)
    return None


def get_shuruq_time(prayer_data: dict) -> datetime | None:
    """Get Shuruq prayer time."""
    timezone = prayer_data.get("timezone")
    shuruq_time = prayer_data.get("shuruq")

    if not timezone:
        _LOGGER.warning("Missing timezone data")
        return None

    if not shuruq_time:
        return None

    day = dt_util.now().date()
    localized_prayer_time = time_with_timezone(timezone, day, shuruq_time)
    if localized_prayer_time:
        return localized_prayer_time.astimezone(dt_util.UTC)
    return None


def get_jumua_time(prayer_data: dict, jumua_name: str) -> datetime | None:
    """Get Jumua prayer time."""
    jumua_time = prayer_data.get(jumua_name)
    timezone = prayer_data.get("timezone")

    if not timezone:
        _LOGGER.warning("Missing timezone data")
        return None

    if not jumua_time:
        return None

    day = get_next_friday()
    localized_prayer_time = time_with_timezone(timezone, day, jumua_time)
    if localized_prayer_time:
        return localized_prayer_time.astimezone(dt_util.UTC)
    return None


def get_iqama_time(prayer_data: dict, prayer_name: str) -> datetime | None:
    # """Get Iqama prayer time."""
    # calendar = prayer_data.get("calendar")
    """Get Iqama prayer time."""
    calendar = prayer_data.get("calendar")
    iqama_calendar = prayer_data.get("iqamaCalendar")
    timezone = prayer_data.get("timezone")

    if not calendar or not iqama_calendar or not timezone:
        _LOGGER.warning("Missing calendar data for %s Iqama", prayer_name)
        return None

    day = dt_util.now().date()

    # Get base prayer time
    prayer_time = extract_time_from_calendar(calendar, prayer_name, day, timezone)
    if not prayer_time:
        return None

    # Get iqama offset
    iqama_offset = extract_time_from_calendar(
        iqama_calendar, prayer_name, day, timezone, mode_iqama=True
    )
    if not iqama_offset:
        return None

    # Add offset to base prayer time
    iqama_time = add_minutes_to_time(prayer_time, iqama_offset)
    if not iqama_time:
        return None

    localized_prayer_time = time_with_timezone(timezone, day, iqama_time)
    if localized_prayer_time:
        return localized_prayer_time.astimezone(dt_util.UTC)
    return None
