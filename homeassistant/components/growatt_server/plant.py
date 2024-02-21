"""Common code for getting Growatt devices."""

import logging

import growattServer

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_PLANT_ID, DEFAULT_PLANT_ID, LOGIN_INVALID_AUTH_CODE

_LOGGER = logging.getLogger(__name__)


def get_plant_id(api: growattServer.GrowattApi, config):
    """Connect to Growatt API."""

    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    if (
        not login_response["success"]
        and login_response["msg"] == LOGIN_INVALID_AUTH_CODE
    ):
        _LOGGER.error("Username, Password or URL may be incorrect!")
        return

    if not login_response["success"] and login_response["msg"] == "507":
        _LOGGER.error(
            "Account has been locked for %s hours", login_response["lockDuration"]
        )
        return

    user_id = login_response["user"]["id"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    return plant_id


def get_device_list(api: growattServer.GrowattApi, config):
    """Retrieve the device list for the selected plant."""

    plant_id = get_plant_id(api, config)

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    return [devices, plant_id]


def get_inverter_list(api: growattServer.GrowattApi, config):
    """Retrieve the device list for the selected plant."""

    plant_id = get_plant_id(api, config)

    # Get a list of inverters for specified plant.
    inverters = api.inverter_list(plant_id)
    return [inverters, plant_id]
