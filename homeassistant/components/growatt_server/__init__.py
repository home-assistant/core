"""The Growatt server PV inverter sensor integration."""

from collections.abc import Mapping
import logging

import growattServer

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


def get_device_list_classic(
    api, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Device list logic for classic API."""
    plant_id = config[CONF_PLANT_ID]

    # Log in to api and fetch first plant if no plant id is defined.
    try:
        login_response = api.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except Exception as ex:
        raise ConfigEntryError(
            f"Error communicating with Growatt API during login: {ex}"
        ) from ex

    if not login_response.get("success"):
        # If we have a message, include it
        msg = login_response.get("msg", "Unknown error")
        if msg == LOGIN_INVALID_AUTH_CODE:
            raise ConfigEntryAuthFailed("Username, Password or URL may be incorrect!")
        raise ConfigEntryError(f"Growatt login failed: {msg}")

    user_id = login_response["user"]["id"]

    if plant_id == DEFAULT_PLANT_ID:
        try:
            plant_info = api.plant_list(user_id)
        except Exception as ex:
            raise ConfigEntryError(
                f"Error communicating with Growatt API during plant list: {ex}"
            ) from ex
        if not plant_info or "data" not in plant_info or not plant_info["data"]:
            raise ConfigEntryError("No plants found for this account.")
        plant_id = plant_info["data"][0].get("plantId")
        if not plant_id:
            raise ConfigEntryError("Plant ID missing in plant info.")

    # Get a list of devices for specified plant to add sensors for.
    try:
        devices = api.device_list(plant_id)
    except Exception as ex:
        raise ConfigEntryError(
            f"Error communicating with Growatt API during device list: {ex}"
        ) from ex
    return devices, plant_id


def get_device_list_v1(
    api, config: Mapping[str, str]
) -> tuple[list[dict[str, str]], str]:
    """Device list logic for Open API V1.

    Note: Plant selection (including auto-selection if only one plant exists)
    is handled in the config flow before this function is called. This function
    only fetches devices for the already-selected plant_id.
    """
    plant_id = config[CONF_PLANT_ID]
    try:
        devices_dict = api.device_list(plant_id)
    except growattServer.GrowattV1ApiError as e:
        raise ConfigEntryError(
            f"API error during device list: {e} (Code: {getattr(e, 'error_code', None)}, Message: {getattr(e, 'error_msg', None)})"
        ) from e
    devices = devices_dict.get("devices", [])
    # Only MIN device (type = 7) support implemented in current V1 API
    supported_devices = [
        {
            "deviceSn": device.get("device_sn", ""),
            "deviceType": "min",
        }
        for device in devices
        if device.get("type") == 7
    ]

    for device in devices:
        if device.get("type") != 7:
            _LOGGER.warning(
                "Device %s with type %s not supported in Open API V1, skipping",
                device.get("device_sn", ""),
                device.get("type"),
            )
    return supported_devices, plant_id


def get_device_list(
    api, config: Mapping[str, str], api_version: str
) -> tuple[list[dict[str, str]], str]:
    """Dispatch to correct device list logic based on API version."""
    if api_version == "v1":
        return get_device_list_v1(api, config)
    if api_version == "classic":
        return get_device_list_classic(api, config)
    raise ConfigEntryError(f"Unknown API version: {api_version}")


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> bool:
    """Set up Growatt from a config entry."""

    config = config_entry.data
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        url = DEFAULT_URL
        new_data = dict(config_entry.data)
        new_data[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    # Determine API version
    if config.get("auth_type") == "api_token":
        api_version = "v1"
        token = config["token"]
        api = growattServer.OpenApiV1(token=token)
    elif config.get("auth_type") == "password":
        api_version = "classic"
        username = config[CONF_USERNAME]
        api = growattServer.GrowattApi(
            add_random_user_id=True, agent_identifier=username
        )
        api.server_url = url
    else:
        raise ConfigEntryError("Unknown authentication type in config entry.")

    devices, plant_id = await hass.async_add_executor_job(
        get_device_list, api, config, api_version
    )

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
        if device["deviceType"] in ["inverter", "tlx", "storage", "mix", "min"]
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
