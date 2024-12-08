"""Module provides utility functions for reading and writing mosque data files.

Used in the Home Assistant Mawaqit integration.
"""

import json
import logging
import os

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from . import mawaqit_wrapper
from .const import (
    CONF_UUID,
    MAWAQIT_ALL_MOSQUES_NN,
    MAWAQIT_API_KEY_TOKEN,
    MAWAQIT_MOSQ_LIST_DATA,
    MAWAQIT_MY_MOSQUE_NN,
    MAWAQIT_PRAY_TIME,
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


def create_data_folder() -> None:
    """Create the data folder if it does not exist."""
    if not os.path.exists(f"{CURRENT_DIR}/data"):
        os.makedirs(f"{CURRENT_DIR}/data")


async def async_write_in_data(hass: HomeAssistant, directory, file_name, data):
    """Write the given data to a specified file in the data folder in the specified directory asynchronously.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        directory (str): The directory where the data folder is located.
        file_name (str): The name of the file to write the data to.
        data (dict): The data to write to the file.

    """

    def write_in_data(directory, file_name, data):
        """Write the given data to a specified file in the data folder in the specified directory."""
        with open(
            f"{directory}/data/{file_name}",
            "w+",
            encoding="utf-8",
        ) as f:
            json.dump(data, f)

    await hass.async_add_executor_job(write_in_data, directory, file_name, data)


async def async_read_in_data(hass: HomeAssistant, directory, file_name):
    """Write the given data to a specified file in the data folder in the specified directory asynchronously.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        directory (str): The directory where the data folder is located.
        file_name (str): The name of the file to write the data to.
        data (dict): The data to write to the file.

    """

    def read_in_data(directory, file_name):
        """Read the given data from a specified file in the data folder in the specified directory."""
        with open(
            f"{directory}/data/{file_name}",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    return await hass.async_add_executor_job(read_in_data, directory, file_name)


async def read_mawaqit_token(hass: HomeAssistant, store: Store | None) -> str:
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


async def cleare_storage_entry(store, key):
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


async def async_clear_data(hass, store, domain):
    """Clear all data from the store and folders."""

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
    await cleare_storage_entry(store, MAWAQIT_ALL_MOSQUES_NN)

    return title, data_entry
