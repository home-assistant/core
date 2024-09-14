"""Module provides utility functions for reading and writing mosque data files.

Used in the Home Assistant Mawaqit integration.
"""

import json
import os

from homeassistant.core import HomeAssistant

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


async def write_all_mosques_NN_file(mosques, hass: HomeAssistant | None) -> None:
    """Write the mosque data to the 'all_mosques_NN.txt' file."""

    def write():
        with open(f"{CURRENT_DIR}/data/all_mosques_NN.txt", "w", encoding="utf-8") as f:
            json.dump(mosques, f)

    if hass is not None:
        if hass is not None:
            await hass.async_add_executor_job(write)


async def read_my_mosque_NN_file(hass: HomeAssistant):
    """Read the mosque data from the 'my_mosque_NN.txt' file."""

    def read():
        with open(f"{CURRENT_DIR}/data/my_mosque_NN.txt", encoding="utf-8") as f:
            return json.load(f)

    return await hass.async_add_executor_job(read)


async def write_my_mosque_NN_file(mosque, hass: HomeAssistant | None) -> None:
    """Write the mosque data to the 'my_mosque_NN.txt' file."""

    def write():
        with open(f"{CURRENT_DIR}/data/my_mosque_NN.txt", "w", encoding="utf-8") as f:
            json.dump(mosque, f)

    if hass is not None:
        await hass.async_add_executor_job(write)


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
