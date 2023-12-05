"""The Shelly Button Manager integration."""
from __future__ import annotations

import asyncio
from typing import cast

from aioshelly.block_device import BlockDevice
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.shelly.coordinator import (
    ShellyCoordinatorBase,
    ShellyEntryData,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ALL_DEVICES_ATTR_DEFAULT_VALUE,
    ALL_DEVICES_ATTR_NAME,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    LOGGER,
    TARGET_DOMAIN,
    TARGET_STATE_ATTR_DEFAULT_VALUE,
    TARGET_STATE_ATTR_NAME,
    ButtonType,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

LOGGER.debug(f"#### Initialization of component {DOMAIN} ####")
DEVICES: list[ShellyCoordinatorBase[BlockDevice]] = []


def get_target_status(target_button_type, generation_number) -> str:
    """get_target_status."""
    # GEN 1: btn_type = toggle,momentary,edge,detached
    # GEN 2: in_mode =  follow,momentary,flip,detached

    if target_button_type == ButtonType.Detached:
        return ButtonType.Detached.value
    if target_button_type == ButtonType.Momentary:
        return ButtonType.Momentary.value
    if target_button_type == ButtonType.Toggle:
        if generation_number == 1:
            return ButtonType.Toggle.value
        return "follow"
    if target_button_type == ButtonType.Edge:
        if generation_number == 1:
            return ButtonType.Edge.value
        return "flip"
    return "toggle"


def change_button_type(shelly_device, target_button_type) -> bool:
    """Change the button type using RPC or REST."""
    device = shelly_device.device
    LOGGER.debug(f"Changing button type to {device.name}")
    target_state = get_target_status(target_button_type, device.gen)

    if device.gen == 1:  # pylint: disable=too-many-nested-blocks
        for relay in device.settings["relays"]:
            LOGGER.debug(f"Button Type before: {relay['btn_type']}")
            asyncio.run(
                device.http_request(
                    "get", "settings/relay/0", {"btn_type": target_state}
                )
            )
            # asyncio.run(device.update_settings())
            # LOGGER.debug(
            #     f"Button Type after: {device.settings['relays'][device_id]['btn_type']}"
            # )
            LOGGER.debug(device.name)
    else:
        if device.connected is None or device.connected is False:
            LOGGER.debug(f"{device.name} is not connected, passing..")
            # shelly_device.entry.async_start_reauth(shelly_device.hass)
            shelly_device.hass.async_create_task(
                shelly_device.entry.async_start_reauth(shelly_device.hass)
            )

            return False

        try:
            config = device.config
            for temp_id in range(3):
                switch_id = f"switch:{temp_id}"
                if switch_id in config:
                    if config[switch_id]["name"]:
                        try:
                            params = {
                                "id": temp_id,
                                "config": {"in_mode": f"{target_state}"},
                            }
                            asyncio.run(device.call_rpc("Switch.SetConfig", params))
                            LOGGER.debug(
                                f", relay {switch_id}: {config[switch_id]['name']} button status: {config[switch_id]['in_mode']}"
                            )
                        except DeviceConnectionError as err:
                            LOGGER.error(err)
                            raise HomeAssistantError(
                                f"Call RPC for {device.name} connection error, method: Switch.SetConfig, params:"
                                f" {params}, error: {repr(err)}"
                            ) from err
                        except RpcCallError as err:
                            raise HomeAssistantError(
                                f"Call RPC for {device.name} connection error, method: Switch.SetConfig, params:"
                                f" {params}, error: {repr(err)}"
                            ) from err
                        except InvalidAuthError:
                            shelly_device.entry.async_start_reauth(shelly_device.hass)
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error(err)
    return True


def print_obj_data(shelly_entry_coordinator) -> int:
    """Print obj data (Temp Func)."""

    string_to_print = shelly_entry_coordinator.name
    # if shelly_entry_coordinator.device.name:
    #    string_to_print += f', device.name {shelly_entry_coordinator.device.name}'
    if shelly_entry_coordinator.device.gen:
        string_to_print += f", gen {shelly_entry_coordinator.device.gen}"
    if shelly_entry_coordinator.model:
        string_to_print += f", model {shelly_entry_coordinator.model}"
    if shelly_entry_coordinator.sw_version:
        string_to_print += f", sw_version {shelly_entry_coordinator.sw_version}"
    # if shelly_entry_coordinator.device.firmware_version:
    #    string_to_print += f', firmware_version {shelly_entry_coordinator.device.firmware_version}'
    # if shelly_entry_coordinator.data:
    #    string_to_print += f' data {shelly_entry_coordinator.data}'
    if shelly_entry_coordinator.device.ip_address:
        string_to_print += f" ip_address {shelly_entry_coordinator.device.ip_address}"

    generation_number = int(shelly_entry_coordinator.device.gen)
    if generation_number == 1:
        if shelly_entry_coordinator.device.settings["device"]:
            device_settings = shelly_entry_coordinator.device.settings["device"]
            string_to_print += f' num_outputs {str(device_settings["num_outputs"])}'

        relays = shelly_entry_coordinator.device.settings["relays"]
        for relay in relays:
            if relay["name"]:
                string_to_print += (
                    f' Relay: {relay["name"]} button status: {relay["btn_type"]}'
                )
    else:
        try:
            config = shelly_entry_coordinator.device.config
            for relay_id in range(3):
                switch_id = f"switch:{relay_id}"
                if switch_id in config:
                    if config[switch_id]["name"]:
                        string_to_print += f", relay {switch_id}: {config[switch_id]['name']} button status: {config[switch_id]['in_mode']}"
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error(err)

        try:
            if shelly_entry_coordinator.connected:
                string_to_print += f" connected {shelly_entry_coordinator.connected}"
        except Exception as err:  # pylint: disable=broad-exception-caught
            LOGGER.error(err)

    LOGGER.error(f"{string_to_print}")
    return generation_number


def action_change_shelly_button_state(
    target_button_type, change_all_devices, devices
) -> None:
    """Aggregate all relevant devices and change their button state."""

    devices_to_change = []
    if change_all_devices:
        devices_to_change = DEVICES
    else:
        for device in DEVICES:
            if device.device_id in devices:
                devices_to_change.append(device)

    for device_to_change in devices_to_change:
        change_button_type(device_to_change, target_button_type)


def init_shelly_devices(hass: HomeAssistant) -> None:
    """Initializing Shelly devices into a list."""  # noqa: D401
    LOGGER.debug("Initializing Shelly devices list")
    config_entry = hass.data[TARGET_DOMAIN][DATA_CONFIG_ENTRY]
    entry_data = cast(dict[str, ShellyEntryData], config_entry)

    LOGGER.debug(f"Shelly devices config entry keys : {config_entry.keys()}")

    for key in config_entry:
        shelly_entry_data = entry_data[key]
        shelly_entry_data_coordinator = None

        # Block or Rest type - Generation 1
        if shelly_entry_data.block:
            # shelly_entry_data_coordinator = cast(
            #     ShellyRestCoordinator, shelly_entry_data.rest
            # )
            shelly_entry_data_coordinator = shelly_entry_data.rest
        # RPC or RPCPolling type - Generation 2
        elif shelly_entry_data.rpc:
            # shelly_entry_data_coordinator = cast(
            #     ShellyRpcCoordinator, shelly_entry_data.rpc
            # )
            shelly_entry_data_coordinator = shelly_entry_data.rpc  # type: ignore[assignment]

        if shelly_entry_data_coordinator and not any(
            device.device_id == shelly_entry_data_coordinator.device_id
            for device in DEVICES
        ):
            DEVICES.append(shelly_entry_data_coordinator)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the service."""

    LOGGER.error("START SETUP")

    def change_buttons_state(call: ServiceCall) -> None:
        # try:
        #     device = shelly_entry_data_rpc.device
        #     asyncio.run(async_turn_on(0, device))
        #     # hass.async_add_job(async_turn_on(0, device))
        #     # await async_turn_on(0, device)
        #     # rpc_result = device.call_rpc("Switch.SetConfig", {"id": 0, "in_mode": "detached"})
        #     # LOGGER.error(f'RPC Result - {rpc_result}')
        # except Exception as err:
        #     LOGGER.error(err)

        target_button_type_value = call.data.get(
            TARGET_STATE_ATTR_NAME, TARGET_STATE_ATTR_DEFAULT_VALUE
        )
        change_all_devices = call.data.get(
            ALL_DEVICES_ATTR_NAME, ALL_DEVICES_ATTR_DEFAULT_VALUE
        )

        devices_to_set = None
        if not change_all_devices:
            devices_to_set = call.data.get("device_id")

        action_change_shelly_button_state(
            ButtonType[target_button_type_value], change_all_devices, devices_to_set
        )

    def reload_service(call: ServiceCall) -> None:
        # pylint: disable-next=global-statement
        global DEVICES  # noqa: PLW0603
        LOGGER.error(f"reload_service {str(call.data)}")
        DEVICES = []
        init_shelly_devices(hass)

    LOGGER.error("MIDDLE SETUP")
    init_shelly_devices(hass)
    hass.services.register(DOMAIN, "change_buttons_state", change_buttons_state)
    hass.services.register(DOMAIN, "reload", reload_service)

    hass.states.set("shelly_button_manager.loaded", "True")
    LOGGER.error("FINISH SETUP")

    # Return boolean to indicate that initialization was successfully.
    return True
