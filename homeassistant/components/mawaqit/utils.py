"""Module provides utility functions for reading and writing mosque data files.

Used in the Home Assistant Mawaqit integration.
"""

import json
import logging
import os

from homeassistant.core import HomeAssistant

from . import mawaqit_wrapper

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
MAWAQIT_API_KEY_TOKEN = "MAWAQIT_API_KEY"
_LOGGER = logging.getLogger(__name__)


async def write_all_mosques_NN_file(mosques, hass: HomeAssistant) -> None:
    """Write the mosque data to the 'all_mosques_NN.txt' file."""

    await async_write_in_data(hass, CURRENT_DIR, "all_mosques_NN.txt", mosques)


async def read_my_mosque_NN_file(hass: HomeAssistant):
    """Read the mosque data from the 'my_mosque_NN.txt' file."""

    def read():
        with open(f"{CURRENT_DIR}/data/my_mosque_NN.txt", encoding="utf-8") as f:
            return json.load(f)

    return await hass.async_add_executor_job(read)


async def write_my_mosque_NN_file(mosque, hass: HomeAssistant) -> None:
    """Write the mosque data to the 'my_mosque_NN.txt' file."""

    await async_write_in_data(hass, CURRENT_DIR, "my_mosque_NN.txt", mosque)


def create_data_folder() -> None:
    """Create the data folder if it does not exist."""
    if not os.path.exists(f"{CURRENT_DIR}/data"):
        os.makedirs(f"{CURRENT_DIR}/data")


async def read_all_mosques_NN_file(hass: HomeAssistant):
    """Read the mosque data from the 'all_mosques_NN.txt' file and return lists of names, UUIDs, and calculation methods."""

    def read():
        name_servers = []
        uuid_servers = []
        CALC_METHODS = []

        with open(f"{CURRENT_DIR}/data/all_mosques_NN.txt", encoding="utf-8") as f:
            dict_mosques = json.load(f)
            for mosque in dict_mosques:
                distance = mosque["proximity"]
                distance = distance / 1000
                distance = round(distance, 2)
                name_servers.extend([mosque["label"] + " (" + str(distance) + "km)"])
                uuid_servers.extend([mosque["uuid"]])
                CALC_METHODS.extend([mosque["label"]])

        return name_servers, uuid_servers, CALC_METHODS

    return await hass.async_add_executor_job(read)


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


async def read_mawaqit_token(hass: HomeAssistant) -> str:
    """Read the Mawaqit API token from an environment variable."""

    def read_token():
        return os.environ.get(MAWAQIT_API_KEY_TOKEN, "")

    return await hass.async_add_executor_job(read_token)


async def write_mawaqit_token(hass: HomeAssistant, mawaqit_token: str) -> None:
    """Write the Mawaqit API token to an environment variable."""

    def write_token(token):
        os.environ[MAWAQIT_API_KEY_TOKEN] = token

    await hass.async_add_executor_job(write_token, mawaqit_token)


async def update_my_mosque_data_files(
    hass: HomeAssistant, dir, mosque_id=None, token=None
):
    """Update the mosque data files with the latest prayer times.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        dir (str): The directory where the data folder is located.
        mosque_id (str, optional): The ID of the mosque. Defaults to None.
        token (str, optional): The Mawaqit API token. Defaults to None.

    """
    _LOGGER.debug("Updating my mosque data files")
    if mosque_id is None:
        my_mosque = await read_my_mosque_NN_file(hass)
        mosque_id = my_mosque["uuid"]

    if token is None:
        token = await read_mawaqit_token(hass)
        if token == "":
            _LOGGER.error("Mawaqit API token not found")
            return

    dict_calendar = await mawaqit_wrapper.fetch_prayer_times(
        mosque=mosque_id, token=token
    )

    await async_write_in_data(hass, dir, "pray_time.txt", dict_calendar)
