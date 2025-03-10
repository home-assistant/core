"""Module provides utility functions for reading and writing mosque data files.

Used in the Home Assistant Mawaqit integration.
"""

from datetime import datetime, timedelta
import logging
import os

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from . import mawaqit_wrapper
from .const import (
    CONF_UUID,
    MAWAQIT_ALL_MOSQUES_NN,
    MAWAQIT_API_KEY_TOKEN,
    MAWAQIT_MOSQ_LIST_DATA,
    MAWAQIT_MY_MOSQUE_NN,
    MAWAQIT_PRAY_TIME,
    PRAYER_NAMES,
    PRAYER_NAMES_IQAMA,
)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

_LOGGER = logging.getLogger(__name__)


async def read_my_mosque_NN_file(store: Store | None):
    """Read the mosque data from the store.

    Args:
        store (Store | None): The storage object to read from.

    Returns:
        The mosque data read from the store.

    """
    return await read_one_element(store, MAWAQIT_MY_MOSQUE_NN)


async def write_my_mosque_NN_file(mosque, store: Store | None) -> None:
    """Write the mosque data to the store.

    Args:
        mosque (dict): The mosque data to write.
        store (Store | None): The storage object to write to.

    """
    await write_one_element(store, MAWAQIT_MY_MOSQUE_NN, mosque)


async def write_all_mosques_NN_file(mosques, store: Store | None) -> None:
    """Write all mosques data to the store.

    Args:
        mosques (dict): The mosques data to write.
        store (Store | None): The storage object to write to.

    """
    await write_one_element(store, MAWAQIT_ALL_MOSQUES_NN, mosques)


async def read_raw_all_mosques_NN_file(store: Store | None):
    """Read the raw mosque data from the store.

    This function acts as a wrapper to read_all_mosques_NN_file,
    ensuring that the data is read in its raw form.

    Args:
        store (Store | None): The storage object to read from.

    Returns:
        The raw mosque data read from the store.

    """
    return await read_all_mosques_NN_file(store, raw=True)


async def read_all_mosques_NN_file(store: Store | None, raw=False):
    """Read all mosques from the store and return their names, UUIDs, and calculation methods.

    Args:
        store (Store | None): The storage object to read from.
        raw (bool): If True, return the raw data from the store.

    Returns:
        tuple: A tuple containing three lists: names of mosques, UUIDs of mosques, and calculation methods.

    """
    dict_mosques = await read_one_element(store, MAWAQIT_ALL_MOSQUES_NN)

    if raw:
        return dict_mosques

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


async def read_pray_time(store: Store | None):
    """Read the prayer time data from the store.

    Args:
        store (Store | None): The storage object to read from.

    Returns:
        The prayer time data read from the store.

    """
    return await read_one_element(store, MAWAQIT_PRAY_TIME)


async def write_pray_time(pray_time, store: Store | None) -> None:
    """Write the prayer time data to the store.

    Args:
        pray_time (dict): The prayer time data to write.
        store (Store | None): The storage object to write to.

    """
    await write_one_element(store, MAWAQIT_PRAY_TIME, pray_time)


async def read_mosq_list_data(store: Store | None):
    """Read the mosque list data from the store.

    Args:
        store (Store | None): The storage object to read from.

    Returns:
        The mosque list data read from the store.

    """
    return await read_one_element(store, MAWAQIT_MOSQ_LIST_DATA)


async def write_mosq_list_data(mosq_list_data, store: Store | None) -> None:
    """Write the mosque list data to the store.

    Args:
        mosq_list_data (dict): The mosque list data to write.
        store (Store | None): The storage object to write to.

    """
    await write_one_element(store, MAWAQIT_MOSQ_LIST_DATA, mosq_list_data)


async def read_mawaqit_token(hass: HomeAssistant | None, store: Store | None) -> str:
    """Read the Mawaqit API token from an environment variable."""

    _LOGGER.debug("Reading Mawaqit token from store")

    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")

    return await read_one_element(store, MAWAQIT_API_KEY_TOKEN)


async def write_mawaqit_token(
    hass: HomeAssistant, store: Store, mawaqit_token: str
) -> None:
    """Write the Mawaqit API token to an environment variable."""

    _LOGGER.debug("Writing Mawaqit token to store")

    await write_one_element(store, MAWAQIT_API_KEY_TOKEN, mawaqit_token)


async def update_my_mosque_data_files(
    hass: HomeAssistant, dir, store, mosque_id=None, token=None
):
    """Update the mosque data files with the latest prayer times.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        dir (str): The directory where the data folder is located.
        mosque_id (str, optional): The ID of the mosque. Defaults to None.
        token (str, optional): The Mawaqit API token. Defaults to None.
        store (Store, optional): The storage object to read the token from. Defaults to None.

    """
    _LOGGER.debug("Updating my mosque data files")
    if mosque_id is None:
        my_mosque = await read_my_mosque_NN_file(store)
        mosque_id = my_mosque["uuid"]

    if token is None:
        if store is None:
            _LOGGER.error("Update Failed : token and store cannot be both None !")
            raise ValueError("token and store cannot be both None !")
        token = await read_mawaqit_token(hass, store)
        if token == "" or token is None:
            _LOGGER.error("Update Failed : Mawaqit API token not found !")
            return

    dict_calendar = await mawaqit_wrapper.fetch_prayer_times(
        mosque=mosque_id, token=token
    )

    await write_pray_time(dict_calendar, store)


async def read_one_element(store, key):
    """Read a single element from the store by key.

    Args:
        store (Store): The storage object to read from.
        key (str): The key of the element to read.

    Returns:
        The value associated with the key, or None if the key does not exist.

    """
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")

    data = await store.async_load()
    if data is None or key not in data:
        return None
    data = data.get(key)
    if data == {} or data is None:
        return None
    _LOGGER.debug("Read %s from store with key = %s ", data, key)
    return data


async def write_one_element(store, key, value):
    """Write a single element to the store by key.

    Args:
        store (Store): The storage object to write to.
        key (str): The key of the element to write.
        value: The value to associate with the key.

    """
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")

    data = await store.async_load()
    if data is None:
        data = {}
    data[key] = value
    _LOGGER.debug("Writing %s to store with key = %s", data, key)
    await store.async_save(data)


async def read_all_elements(store):
    """Read all elements from the store.

    Args:
        store (Store): The storage object to read from.

    Returns:
        dict: The data read from the store, or an empty dictionary if no data is found.

    """
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")

    data = await store.async_load()
    if data is None:
        return {}
    _LOGGER.debug("Read %s from store", data)
    return data


async def write_all_elements(store, data):
    """Write all elements to the store.

    Args:
        store (Store): The storage object to write to.
        data (dict): The data to write to the store.

    """
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")

    _LOGGER.debug("Writing %s to store", data)
    await store.async_save(data)


async def clear_storage_entry(store, key):
    """Clear the storage entry.

    Args:
        store (Store): The storage object to clear.
        key (str): The key of the element to clear.

    """
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")
    await write_one_element(
        store,
        key,
        None,
    )
    _LOGGER.info("Cleared storage entry with key = %s", key)
    # maybe use the async_remove() in the store object


async def async_clear_data(hass: HomeAssistant, store: Store | None, domain: str):
    """Clear all data from the store and folders."""
    if store is None:
        _LOGGER.error("Store is None !")
        raise ValueError("Store is None !")
    # Remove all config entries
    entries = hass.config_entries.async_entries(domain)
    for entry in entries:
        if entry.domain == domain:
            await hass.config_entries.async_remove(entry.entry_id)

    await store.async_remove()  # Remove the existing data in the store


async def is_already_configured(hass: HomeAssistant, store: Store) -> bool:
    """Check if the mosque configuration file already exists."""
    return await read_my_mosque_NN_file(store) is not None


async def is_another_instance(hass: HomeAssistant, store: Store) -> bool:
    """Check if another instance of the mosque configuration exists."""
    return await is_already_configured(hass, store)


async def async_save_mosque(
    hass: HomeAssistant,
    store: Store | None,
    UUID,
    mawaqit_token=None,
    lat=None,
    longi=None,
) -> tuple[str, dict]:
    """Save mosque data  in store and prepare entry data.

    This function saves mosque data by reading from the store, updating necessary files,
    and clearing storage entries. It also handles optional latitude and longitude data,
    and prepares the entry data.

    Args:
        hass (HomeAssistant): The HomeAssistant instance.
        store (Store): The storage instance to read/write data.
        UUID (str): The unique identifier for the mosque.
        mawaqit_token (str, optional): The token for Mawaqit API. Defaults to None.
        lat (float, optional): The latitude of the mosque. Defaults to None.
        longi (float, optional): The longitude of the mosque. Defaults to None.

    Returns:
        tuple: A tuple containing the title and data entry dictionary.

    """
    if store is None:
        _LOGGER.error("Store should not be None !")
        raise ValueError("Store should not be None !")

    if mawaqit_token is None:
        mawaqit_token = await read_mawaqit_token(hass, store)

    name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(store)
    raw_all_mosques_data = await read_raw_all_mosques_NN_file(store)

    mosque = UUID
    index = name_servers.index(mosque)
    mosque_id = uuid_servers[index]

    await write_my_mosque_NN_file(raw_all_mosques_data[index], store)

    await update_my_mosque_data_files(
        hass,
        CURRENT_DIR,
        store,
        mosque_id=mosque_id,
        token=mawaqit_token,
    )

    title = "MAWAQIT" + " - " + raw_all_mosques_data[index]["name"]
    data_entry = {
        CONF_API_KEY: mawaqit_token,
        CONF_UUID: mosque_id,
    }
    if lat is not None and longi is not None:
        data_entry[CONF_LATITUDE] = lat
        data_entry[CONF_LONGITUDE] = longi
    await clear_storage_entry(store, MAWAQIT_ALL_MOSQUES_NN)

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
    """Return the date of the next Friday from today.

    If today is Friday, return the next Friday.

    :return: A datetime.date object representing the next Friday.
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
