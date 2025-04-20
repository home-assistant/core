"""The Growatt server PV inverter sensor integration."""

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import (
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
)
from .coordinator import GrowattCoordinator


def get_device_list(api, config):
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    if (
        not login_response["success"]
        and login_response["msg"] == LOGIN_INVALID_AUTH_CODE
    ):
        raise ConfigEntryError("Username, Password or URL may be incorrect!")
    user_id = login_response["user"]["id"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    return [devices, plant_id]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Growatt from a config entry."""
    config = {**config_entry.data}
    username = config[CONF_USERNAME]
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        url = DEFAULT_URL
        config[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=config)

    # Initialise the library with the username & a random id each time it is started
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id
    )

    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "total": total_coordinator,
        "devices": {},
    }

    # Create coordinators for each device
    for device in devices:
        device_type = device["deviceType"]
        if device_type in ["inverter", "tlx", "storage", "mix"]:
            device_coordinator = GrowattCoordinator(
                hass, config_entry, device["deviceSn"], device_type, plant_id
            )
            hass.data[DOMAIN][config_entry.entry_id]["devices"][device["deviceSn"]] = (
                device_coordinator
            )

    # Set up all the entities
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
