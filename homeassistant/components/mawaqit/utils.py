"""Utility functions for the Mawaqit integration."""

from datetime import date, datetime, timedelta
import logging
import re

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_UUID
import homeassistant.util.dt as dt_util

from .const import PRAYER_NAMES, PRAYER_NAMES_IQAMA

_LOGGER = logging.getLogger(__name__)

_TIME_ABSOLUTE_RE = re.compile(r"^\d{2}:\d{2}$")  # Matches HH:MM format


def save_mosque(
    mosque_display_name: str,
    mosque_id: str,
    mawaqit_token: str | None = None,
    lat: float | None = None,
    longi: float | None = None,
) -> tuple[str, dict]:
    """Create a data entry to simplify the process of saving mosque data.

    Args:
        mosque_display_name (str): The display name of the mosque.
        mosque_id (str): The unique ID of the mosque.
        mawaqit_token (str, optional): Token for Mawaqit API authentication.
        lat (float, optional): Latitude of the mosque.
        longi (float, optional): Longitude of the mosque.

    Returns:
        tuple[str, dict]: A tuple containing the title and data entry dictionary.

    """

    if mawaqit_token is None:
        _LOGGER.error("Token should not be None !")
        raise ValueError("Token should not be None !")

    title = "MAWAQIT" + " - " + mosque_display_name
    data_entry: dict[str, str | float] = {
        CONF_API_KEY: mawaqit_token,
        CONF_UUID: mosque_id,
    }
    if lat is not None and longi is not None:
        data_entry[CONF_LATITUDE] = lat
        data_entry[CONF_LONGITUDE] = longi

    return title, data_entry


def extract_time_from_calendar(
    calendar: list[dict[str, list[str]]],
    prayer_name: str,
    target_date: date,
    mode_iqama: bool = False,
) -> str | None:
    """Extract the time of a specific prayer for a given date.

    :param calendar: List containing 12 dictionaries (one for each month).
    :param prayer_name: The name of the prayer to extract (e.g., "Fajr", "Dhuhr").
    :param target_date: The date for which to extract the prayer time (datetime.date object).
    :param mode_iqama: Whether to extract iqama times instead of prayer times.
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


def time_with_timezone(
    timezone: str, target_date: str | date, time: str
) -> datetime | None:
    """Convert a naive datetime to a timezone-aware datetime.

    Args:
        timezone (str): The timezone string (e.g., "Europe/Paris").
        target_date (str | date): The date in "YYYY-MM-DD" format.
        time (str): The time string in "HH:MM" format.

    Returns:
        datetime: The timezone-aware datetime object, or None if the timezone is invalid.

    """
    tz = dt_util.get_time_zone(timezone)
    if not tz:
        _LOGGER.error("Invalid timezone: %s", timezone)
        return None
    naive_time = datetime.strptime(f"{target_date} {time}", "%Y-%m-%d %H:%M")
    return dt_util.as_local(naive_time.replace(tzinfo=tz))


def _to_utc(timezone: str, day: date, time_str: str) -> datetime | None:
    """Localize a HH:MM time string on a given date and return it in UTC."""
    if not time_str:
        return None
    localized = time_with_timezone(timezone, day, time_str)
    if localized:
        return localized.astimezone(dt_util.UTC)
    return None


def add_minutes_to_time(time_str: str, minutes_str: str) -> str | None:
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
        raise ValueError(f"Invalid minutes format, expected '+xx' got '{minutes_str}'")

    try:
        minutes_to_add = int(minutes_str[1:])  # Extract the integer part

        # Add minutes
        new_time = base_time + timedelta(minutes=minutes_to_add)

        # Format back to string
        return new_time.strftime("%H:%M")

    except (ValueError, TypeError) as e:
        _LOGGER.error("Error in add_minutes_to_time: %s", e)
        return None


def parse_iqama_time(prayer_time: str, iqama_value: str) -> str | None:
    """Return the iqama time as HH:MM.

    Handles two formats:
    - '+xx' : offset in minutes from the prayer time (e.g. '+5', '+15')
    - 'HH:MM': absolute time in mosque local timezone (e.g. '04:32')
    """
    if not iqama_value:
        return None

    if iqama_value.startswith("+"):
        return add_minutes_to_time(prayer_time, iqama_value)

    # If it's not an offset, it should be an absolute time in HH:MM format
    if _TIME_ABSOLUTE_RE.match(iqama_value):
        return iqama_value

    _LOGGER.error("Unrecognised iqama format: %s", iqama_value)
    return None


def compute_islamic_midnight(
    prayer_data: dict, target_date: date, timezone: str
) -> datetime | None:
    """Return the Islamic midnight for a given date.

    Islamic midnight is the midpoint between Isha of `target_date` and Fajr of
    the following day.  It is always timezone-aware and expressed in the
    mosque's local timezone.

    Args:
        prayer_data: Full prayer data dict (must contain a ``calendar`` key).
        target_date: Civil date (datetime.date) whose Isha starts the interval.
        timezone:    IANA timezone string (e.g. ``"Africa/Casablanca"``).

    Returns:
        Timezone-aware datetime, or None when Isha / Fajr data are unavailable.
    """
    calendar = prayer_data.get("calendar")
    if not calendar:
        return None

    next_day = target_date + timedelta(days=1)

    isha_str = extract_time_from_calendar(calendar, "isha", target_date)
    fajr_str = extract_time_from_calendar(calendar, "fajr", next_day)

    if not isha_str or not fajr_str:
        _LOGGER.warning(
            "Cannot compute Islamic midnight for %s: missing Isha or Fajr time",
            target_date,
        )
        return None

    isha_dt = time_with_timezone(timezone, target_date, isha_str)
    fajr_dt = time_with_timezone(timezone, next_day, fajr_str)

    if not isha_dt or not fajr_dt:
        return None

    return isha_dt + (fajr_dt - isha_dt) / 2


def get_islamic_date(prayer_data: dict, timezone: str) -> date:
    """Return the civil date that corresponds to the current Islamic day.

    The Islamic day advances at Islamic midnight (the midpoint between
    yesterday's Isha and today's Fajr).  Before that point (even though the
    clock has already ticked past 00:00) we are still in the previous Islamic day.

    Args:
        prayer_data: Full prayer data dict.
        timezone:    IANA timezone string.

    Returns:
        datetime.date for the active Islamic day, or civil today as fallback.
    """
    tz = dt_util.get_time_zone(timezone)
    now = dt_util.now(tz) if tz else dt_util.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    islamic_midnight = compute_islamic_midnight(prayer_data, yesterday, timezone)

    if islamic_midnight is None:
        _LOGGER.warning(
            "Could not compute Islamic midnight for %s — falling back to civil date",
            yesterday,
        )
        return today

    # both now and islamic_midnight are timezone-aware so they can be compared directly
    return today if now >= islamic_midnight else yesterday


def get_next_friday() -> date:
    """Return the date of the next Friday after today.

    This function always returns the Friday of the following week if today is Friday,
    i.e., it never returns today's date. If today is any other day, it returns the upcoming Friday.

    :return: A datetime.date object representing the next Friday (never today).
    """
    today = dt_util.now().date()
    days_until_friday = (
        4 - today.weekday()
    ) % 7  # 4 represents Friday (Monday=0, ..., Sunday=6)

    if days_until_friday == 0:  # If today is Friday, move to next week
        days_until_friday = 7

    return today + timedelta(days=days_until_friday)


def get_prayer_times_for_two_days(
    prayer_calendar: list[dict[str, list[str]]], today: datetime, timezone: str
) -> dict[str, dict[str, str | list[str]]]:
    """Extract prayer times for today and tomorrow from the provided calendar.

    Args:
        prayer_calendar (dict): The yearly prayer times calendar.
        today (datetime): The datetime object representing 'today', not timezone-aware.
        timezone (str): String representing the timezone, e.g., 'Europe/Paris'.

    Returns:
        dict: A dictionary containing prayer times for today and tomorrow.

    """
    tz = dt_util.get_time_zone(timezone)
    today = today.astimezone(tz)
    tomorrow = today + timedelta(days=1)

    # Extracting times for today and tomorrow
    today_times = prayer_calendar[today.month - 1].get(str(today.day), [])
    tomorrow_times = prayer_calendar[tomorrow.month - 1].get(str(tomorrow.day), [])

    return {
        "today": {"date": today.strftime("%Y-%m-%d"), "prayer_times": today_times},
        "tomorrow": {
            "date": tomorrow.strftime("%Y-%m-%d"),
            "prayer_times": tomorrow_times,
        },
    }


def find_next_prayer(
    current_time: datetime,
    prayer_calendar: list[dict[str, list[str]]],
    timezone: str,
) -> tuple[int | None, datetime | None]:
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

    current_time = current_time.astimezone(tz)

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

    if next_prayer_datetime is not None:
        next_prayer_datetime = next_prayer_datetime.astimezone(dt_util.UTC)

    return next_prayer_index, next_prayer_datetime


def get_regular_prayer_time(prayer_data: dict, prayer_name: str) -> datetime | None:
    """Get regular prayer time (Fajr, Dhuhr, Asr, Maghrib, Isha)."""
    calendar = prayer_data.get("calendar")
    timezone = prayer_data.get("timezone")

    if not calendar or not timezone:
        _LOGGER.warning("Missing calendar or timezone data for %s", prayer_name)
        return None

    day = get_islamic_date(prayer_data, timezone)
    prayer_time = extract_time_from_calendar(calendar, prayer_name, day)

    return _to_utc(timezone, day, prayer_time) if prayer_time else None


def get_shuruq_time(prayer_data: dict) -> datetime | None:
    """Get Shuruq time."""
    timezone = prayer_data.get("timezone")
    shuruq_time = prayer_data.get("shuruq")

    if not timezone:
        _LOGGER.warning("Missing timezone data")
        return None

    day = get_islamic_date(prayer_data, timezone)
    return _to_utc(timezone, day, shuruq_time) if shuruq_time else None


def get_jumua_time(prayer_data: dict, jumua_name: str) -> datetime | None:
    """Get Jumua prayer time."""
    jumua_time = prayer_data.get(jumua_name)
    timezone = prayer_data.get("timezone")

    if not timezone:
        _LOGGER.warning("Missing timezone data")
        return None

    return _to_utc(timezone, get_next_friday(), jumua_time) if jumua_time else None


def get_iqama_time(prayer_data: dict, prayer_name: str) -> datetime | None:
    """Get Iqama prayer time."""
    calendar = prayer_data.get("calendar")
    iqama_calendar = prayer_data.get("iqamaCalendar")
    timezone = prayer_data.get("timezone")

    if not calendar or not iqama_calendar or not timezone:
        _LOGGER.warning("Missing calendar data for %s Iqama", prayer_name)
        return None

    day = get_islamic_date(prayer_data, timezone)

    # Get base prayer time
    prayer_time = extract_time_from_calendar(calendar, prayer_name, day)
    if not prayer_time:
        return None

    # Get iqama data and compute iqama time
    iqama_raw = extract_time_from_calendar(
        iqama_calendar, prayer_name, day, mode_iqama=True
    )
    if not iqama_raw:
        return None

    iqama_time = parse_iqama_time(prayer_time, iqama_raw)
    if not iqama_time:
        return None

    return _to_utc(timezone, day, iqama_time)
