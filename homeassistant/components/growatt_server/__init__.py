"""The Growatt server PV inverter sensor integration."""

from __future__ import annotations

from datetime import datetime
import logging

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import (
    BATT_MODE_MAP,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_URL,
    DEPRECATED_URLS,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    PLATFORMS,
)
from .coordinator import GrowattCoordinator

_LOGGER = logging.getLogger(__name__)


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
        _LOGGER.warning(
            "URL: %s has been deprecated, migrating to the latest default: %s",
            url,
            DEFAULT_URL,
        )
        url = DEFAULT_URL
        config[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=config)

    # Initialize the Growatt API to fetch the device list and plant ID
    api = await hass.async_add_executor_job(growattServer.GrowattApi, True, username)
    api.server_url = url

    devices, plant_id = await hass.async_add_executor_job(get_device_list, api, config)

    # Create a coordinator for the total sensors
    total_coordinator = GrowattCoordinator(
        hass, config_entry, plant_id, "total", plant_id
    )
    await total_coordinator.async_config_entry_first_refresh()

    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "total": total_coordinator,
        "devices": {},
    }

    # Create a coordinator for each supported device type
    for device in devices:
        device_type = device["deviceType"]
        if device_type not in ["inverter", "tlx", "storage", "mix"]:
            continue
        device_coordinator = GrowattCoordinator(
            hass, config_entry, device["deviceSn"], device["deviceType"], plant_id
        )
        await device_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][config_entry.entry_id]["devices"][device["deviceSn"]] = (
            device_coordinator
        )

        if device_type == "tlx":

            async def handle_update_tlx_inverter_time_segment(
                call, device_coordinator=device_coordinator
            ):
                segment_id = call.data["segment_id"]
                batt_mode_str = call.data["batt_mode"]
                start_time_str = call.data["start_time"]
                end_time_str = call.data["end_time"]
                enabled = call.data["enabled"]

                if not (1 <= segment_id <= 9):
                    raise HomeAssistantError("segment_id must be between 1 and 9")

                # Convert batt_mode to the corresponding constant
                batt_mode = BATT_MODE_MAP.get(batt_mode_str)
                if batt_mode is None:
                    _LOGGER.error("Invalid battery mode: %s", batt_mode_str)
                    raise HomeAssistantError(f"Invalid battery mode: {batt_mode_str}")

                try:
                    # Convert start_time and end_time to datetime.time objects
                    start_time = datetime.strptime(start_time_str, "%H:%M").time()
                    end_time = datetime.strptime(end_time_str, "%H:%M").time()
                except ValueError:
                    _LOGGER.error("Start_time and end_time must in HH:MM format")
                    raise HomeAssistantError(
                        "start_time and end_time must be in HH:MM format"
                    ) from None

                if not isinstance(enabled, bool):
                    raise HomeAssistantError(
                        "enabled must be a boolean value (True or False)"
                    )

                try:
                    await device_coordinator.update_tlx_inverter_time_segment(
                        segment_id,
                        batt_mode,
                        start_time,
                        end_time,
                        enabled,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Error updating TLX inverter time segment: %s", err)
                    raise HomeAssistantError(
                        f"Error updating TLX inverter time segment: {err}"
                    ) from None

            hass.services.async_register(
                DOMAIN,
                "update_tlx_inverter_time_segment",
                handle_update_tlx_inverter_time_segment,
            )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
