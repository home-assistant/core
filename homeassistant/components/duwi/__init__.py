"""Support for Duwi Smart devices."""

import asyncio
import logging

from duwi_smarthome_sdk.api.discover import DiscoverClient
from duwi_smarthome_sdk.api.group import GroupClient
from duwi_smarthome_sdk.api.floor import FloorInfoClient
from duwi_smarthome_sdk.api.room import RoomInfoClient
from duwi_smarthome_sdk.api.terminal import TerminalClient
from duwi_smarthome_sdk.api.ws import DeviceSynchronizationWS
from duwi_smarthome_sdk.model.resp.device import Device
from duwi_smarthome_sdk.model.resp.group import Group
from duwi_smarthome_sdk.const.status import Code
from duwi_smarthome_sdk.const.type_map import type_map, group_type_map

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    APP_VERSION,
    CLIENT_MODEL,
    CLIENT_VERSION,
    DOMAIN,
    SUPPORTED_PLATFORMS,
)
from .util import persist_messages_with_status_code, trans_duwi_state_to_ha_state

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(domain=DOMAIN)


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    """
    Set up the Duwi Smart Devices integration.

    This method prepares the integration to be configured by checking for existing
    config entries and initiating the config flow if none are found.

    Parameters:
    - hass: HomeAssistant instance.
    - hass_config: Configuration dictionary.

    Returns:
    - Boolean indicating successful setup.
    """

    # Check for existing config entries for this integration
    if not hass.config_entries.async_entries(DOMAIN):
        # No entries found, initiate the configuration flow
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    # Setup was successful
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Set up a Duwi Smart Hub config entry.

    This method initializes the necessary data structures and starts the discovery
    process using the DiscoverClient with the provided credentials from the config entry.

    Parameters:
    - hass: HomeAssistant instance for the current Home Assistant run.
    - config_entry: ConfigEntry instance containing configuration data from the user.

    Returns:
    - True if the setup was successful.
    """

    # Extract the entry ID to use it as an instance identifier.
    instance_id = config_entry.entry_id

    # Create or ensure the primary domain data structure is present in hass.data.
    hass.data.setdefault(DOMAIN, {})

    # Clear old data for this instance, if any.
    hass.data[DOMAIN].pop(instance_id, None)
    terminals_dict = {}

    hass.data[DOMAIN].setdefault(
        instance_id,
        {
            "devices": {},  # Placeholder for devices dictionary to be populated
        },
    )

    # Add the new house number to the list of existing houses.
    hass.data[DOMAIN].setdefault("existing_house", []).append(
        config_entry.data.get("house_no")
    )

    # Store the configuration entry data for easy access.
    entry_data = hass.data[DOMAIN][instance_id]
    entry_data.update(
        {
            "app_key": config_entry.data.get("app_key").strip(),
            "app_secret": config_entry.data.get("app_secret").strip(),
            "access_token": config_entry.data.get("access_token").strip(),
            "refresh_token": config_entry.data.get("refresh_token").strip(),
            "house_no": config_entry.data.get("house_no").strip(),
        }
    )
    _LOGGER.debug(f"Config entry data: {entry_data}")
    # Initialize the client used for discovering devices with credentials from entry_data.
    discover_client = DiscoverClient(
        app_key=entry_data["app_key"],
        app_secret=entry_data["app_secret"],
        access_token=entry_data["access_token"],
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    # Initialize the client used for discovering group with credentials from entry_data.
    group_client = GroupClient(
        app_key=entry_data["app_key"],
        app_secret=entry_data["app_secret"],
        access_token=entry_data["access_token"],
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    # Begin the discovery process using the discovery client.
    devices_status, devices = await discover_client.discover(
        house_no=entry_data["house_no"]
    )
    groups_status, groups = await group_client.discover_groups(
        house_no=entry_data["house_no"]
    )
    # Initialize clients for fetching floor, room, and terminal information.
    floor_info_client = FloorInfoClient(
        app_key=entry_data["app_key"],
        app_secret=entry_data["app_secret"],
        access_token=entry_data["access_token"],
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    room_info_client = RoomInfoClient(
        app_key=entry_data["app_key"],
        app_secret=entry_data["app_secret"],
        access_token=entry_data["access_token"],
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    terminal_client = TerminalClient(
        app_key=entry_data["app_key"],
        app_secret=entry_data["app_secret"],
        access_token=entry_data["access_token"],
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    # Fetch additional data: floor, room, and terminal information.
    floors_status, floors = await floor_info_client.fetch_floor_info(
        entry_data["house_no"]
    )
    rooms_status, rooms = await room_info_client.fetch_room_info(entry_data["house_no"])
    terminals_status, terminals = await terminal_client.fetch_terminal_info(
        entry_data["house_no"]
    )

    if floors_status != Code.SUCCESS.value:
        _LOGGER.error("Failed to fetch floor information")
        floors = []

    if rooms_status != Code.SUCCESS.value:
        _LOGGER.error("Failed to fetch room information")
        rooms = []

    if terminals_status != Code.SUCCESS.value:
        _LOGGER.error("Failed to fetch terminal information")
        terminals = []

    # Process terminal information for enhanced device accuracy.
    if terminals is not None:
        for terminal in terminals:
            # Mapping of Host to Slave.
            if terminal.host_sequence != terminal.terminal_sequence:
                # Add this Slave into the Host's Slave list.
                terminals_dict.setdefault(terminal.host_sequence, []).append(
                    terminal.terminal_sequence
                )
                # Set the Slave's is_follow_online flag, whether the device will follow the slave online together.
                hass.data[DOMAIN][instance_id].setdefault("slave", {}).setdefault(
                    terminal.terminal_sequence,
                    {"is_follow_online": terminal.is_follow_online},
                )

        hass.data[DOMAIN][instance_id].setdefault("host", terminals_dict)

    # Create mapping dictionaries for floors and rooms for efficient data lookups.
    floors_dict = (
        {floor.floor_no: floor.floor_name for floor in floors} if floors else {}
    )
    rooms_floors_dict = {room.room_no: room.floor_no for room in rooms} if rooms else {}
    rooms_dict = {room.room_no: room.room_name for room in rooms} if rooms else {}

    # Assign floor and room names to each device based on the mapping.
    for device in devices if devices else []:
        device.floor_name = floors_dict.get(
            rooms_floors_dict.get(device.room_no), device.floor_name
        )
        device.room_name = rooms_dict.get(device.room_no, device.room_name)

    for group in groups if groups else []:
        group.floor_name = floors_dict.get(
            rooms_floors_dict.get(group.room_no), group.floor_name
        )
        group.room_name = rooms_dict.get(group.room_no, group.room_name)
        if group.floor_name is None:
            group.floor_name = ""
        if group.room_name is None:
            group.room_name = ""

    # Register devices within Home Assistant if the discovery was successful.
    if devices_status == Code.SUCCESS.value:
        device_registry = setup_device_registry(devices)
        hass.data[DOMAIN][instance_id]["devices"] = device_registry

    if groups_status == Code.SUCCESS.value:
        group_registry = setup_group_registry(
            groups, hass.data[DOMAIN][instance_id].get("devices")
        )
        hass.data[DOMAIN][instance_id]["devices"] = group_registry

    # Forward the setup process to supported platforms within this integration.
    await hass.config_entries.async_forward_entry_setups(
        config_entry, SUPPORTED_PLATFORMS
    )

    # WebSocket callback for real-time device state updates.
    async def on_callback(message: str):
        await trans_duwi_state_to_ha_state(hass, instance_id, message)

    # Initialize WebSocket for real-time synchronization.
    ws_sync = DeviceSynchronizationWS(
        on_callback=on_callback,
        app_key=config_entry.data.get("app_key"),
        app_secret=config_entry.data.get("app_secret"),
        access_token=config_entry.data.get("access_token"),
        refresh_token=config_entry.data.get("refresh_token"),
        house_no=config_entry.data.get("house_no"),
        app_version=APP_VERSION,
        client_version=CLIENT_VERSION,
        client_model=CLIENT_MODEL,
    )

    # Establish WebSocket connection and set up listeners for device updates.
    await ws_sync.reconnect()
    listen_task = hass.loop.create_task(ws_sync.listen())
    keep_alive_task = hass.loop.create_task(ws_sync.keep_alive())
    refresh_token_task = hass.loop.create_task(ws_sync.refresh_token())
    hass.data[DOMAIN][instance_id].setdefault(
        "ws",
        {
            "ws_sync": ws_sync,
            "listen_task": listen_task,
            "keep_alive_task": keep_alive_task,
            "refresh_token_task": refresh_token_task,
        },
    )

    # Perform clean-up after successful setup.
    hass.data[DOMAIN][instance_id].pop("devices", None)

    # Record setup completion and device registry initialization.
    await persist_messages_with_status_code(
        hass=hass,
        status=instance_id,
        message="Successfully initialized Duwi Smart Hub. Your house's name is: "
        + config_entry.data.get("house_name"),
    )

    return True


def setup_device_registry(devices: Device, device_registry=None):
    """Organize devices into a structured registry."""
    if device_registry is None:
        device_registry = {}
    for device in devices:
        for main_type, type_no_map in type_map.items():
            if (
                device.device_type_no in type_no_map
                and not device.device_type_no.startswith(const.SENSOR_TYPE)
            ):
                device_registry.setdefault(main_type, {}).setdefault(
                    type_no_map[device.device_type_no], []
                ).append(device)

    return device_registry


def setup_group_registry(groups: Group, group_registry=None):
    """Organize groups into a structured registry."""
    if group_registry is None:
        group_registry = {}
    for group in groups:
        for main_type, type_no_map in group_type_map.items():
            if group.device_group_type in type_no_map:
                group_registry.setdefault(main_type, {}).setdefault(
                    type_no_map[group.device_group_type], []
                ).append(group)
    return group_registry


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a Duwi Smart Hub config entry."""

    # Attempt to unload all platforms associated with the entry.
    return await hass.config_entries.async_unload_platforms(
        config_entry, SUPPORTED_PLATFORMS
    )


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Remove a Duwi Smart Hub config entry and its associated data."""

    house_no = config_entry.data.get("house_no")

    # Remove the house number from the existing houses list, if present.
    if house_no in hass.data[DOMAIN].get("existing_house", []):
        hass.data[DOMAIN]["existing_house"].remove(house_no)

    # Close the websocket connection if it exists.
    # Retrieve instance-specific data from the Home Assistant global data store.
    entry_data = hass.data[DOMAIN].get(config_entry.entry_id)
    if entry_data is not None:  # If instance data exists, proceed.
        ws = entry_data.get("ws")  # Fetch WebSocket details.
        if ws:
            ws_sync = ws.get("ws_sync")  # Obtain the synchronous WebSocket object.
            if ws_sync:
                try:
                    await ws_sync.disconnect()  # Attempt to disconnect the WebSocket.
                    _LOGGER.info(
                        "WebSocket connection closed."
                    )  # Log successful disconnect.
                except (
                    Exception
                ) as exc:  # Catch and log any exceptions during disconnect.
                    _LOGGER.error(f"Error disconnecting WebSocket: {exc}")

            # Define an array of task names that the WebSocket may have started.
            for task_name in ["listen_task", "keep_alive_task", "refresh_token_task"]:
                task = ws.get(task_name)  # Retrieve task.
                if task:  # If task exists, check its state.
                    if not task.done():  # If task is not finished, cancel it.
                        task.cancel()
                        try:
                            await task  # Wait for task to handle the cancellation.
                        except asyncio.CancelledError:  # Handle task cancellation.
                            _LOGGER.debug(
                                f"{task_name} cancellation completed."
                            )  # Confirm cancellation.
                        except (
                            Exception
                        ) as exc:  # Catch any exceptions during cancellation.
                            _LOGGER.error(f"Error in finalising {task_name}: {exc}")
                    else:
                        # If the task had already reached completion, log this information.
                        _LOGGER.debug(f"{task_name} was already completed.")

    # Finally, remove the entry's data from the domain's storage.
    hass.data[DOMAIN].pop(config_entry.entry_id, None)

    return True
