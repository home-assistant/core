"""The Growatt server PV inverter sensor integration."""

from collections.abc import Mapping
import logging

import growattServer
import requests

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError

from .const import (
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
)
from .coordinator import GrowattConfigEntry, GrowattCoordinator
from .models import GrowattRuntimeData

_LOGGER = logging.getLogger(__name__)


def get_device_list(
    api: growattServer.GrowattApi, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Retrieve the device list for the selected plant."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    try:
        login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except requests.exceptions.RequestException as ex:
        raise ConfigEntryError(f"Network error during Growatt API login: {ex}") from ex
    except ValueError as ex:
        raise ConfigEntryError(f"Invalid response format during login: {ex}") from ex
    except KeyError as ex:
        raise ConfigEntryError(f"Missing expected key in login response: {ex}") from ex

    if not login_response.get("success"):
        msg = login_response.get("msg", "Unknown error")
        _LOGGER.debug("Growatt login failed: %s", msg)
        if msg == LOGIN_INVALID_AUTH_CODE:
            raise ConfigEntryAuthFailed("Username, Password or URL may be incorrect!")
        raise ConfigEntryError(f"Growatt login failed: {msg}")

    try:
        user_id = login_response["user"]["id"]
    except KeyError as ex:
        raise ConfigEntryError(f"Missing user ID in login response: {ex}") from ex

    if plant_id == DEFAULT_PLANT_ID:
        try:
            plant_info = api.plant_list(user_id)
        except requests.exceptions.RequestException as ex:
            raise ConfigEntryError(f"Network error during plant list: {ex}") from ex
        except ValueError as ex:
            raise ConfigEntryError(
                f"Invalid response format during plant list: {ex}"
            ) from ex
        except KeyError as ex:
            raise ConfigEntryError(
                f"Missing expected key in plant list response: {ex}"
            ) from ex

        if not plant_info or "data" not in plant_info or not plant_info["data"]:
            raise ConfigEntryError("No plants found for this account.")
        plant_id = plant_info["data"][0].get("plantId")
        if not plant_id:
            raise ConfigEntryError("Plant ID missing in plant info.")

    try:
        devices = api.device_list(plant_id)
    except requests.exceptions.RequestException as ex:
        raise ConfigEntryError(f"Network error during device list: {ex}") from ex
    except ValueError as ex:
        raise ConfigEntryError(
            f"Invalid response format during device list: {ex}"
        ) from ex
    except KeyError as ex:
        raise ConfigEntryError(
            f"Missing expected key in device list response: {ex}"
        ) from ex

    return devices, plant_id


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Set up Growatt from a config entry."""
    config = config_entry.data
    username = config[CONF_USERNAME]
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        url = DEFAULT_URL
        new_data = dict(config_entry.data)
        new_data[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Initialise the library with the username & a random id each time it is started
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id
    )

    # Create coordinators for each device
    device_coordinators = {
        device["deviceSn"]: GrowattCoordinator(
            hass, config_entry, device["deviceSn"], device["deviceType"], plant_id
        )
        for device in devices
        if device["deviceType"] in ["inverter", "tlx", "storage", "mix"]
    }

    # Perform the first refresh for the total coordinator
    await total_coordinator.async_config_entry_first_refresh()

    # Perform the first refresh for each device coordinator
    for device_coordinator in device_coordinators.values():
        await device_coordinator.async_config_entry_first_refresh()

    # Store runtime data in the config entry
    config_entry.runtime_data = GrowattRuntimeData(
        total_coordinator=total_coordinator,
        devices=device_coordinators,
    )

    # Set up all the entities
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
