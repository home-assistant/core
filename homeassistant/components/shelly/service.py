"""The Shelly Service component."""
from __future__ import annotations

from typing import cast

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util.read_only_dict import ReadOnlyDict

from .const import (
    ALL_DEVICES_ATTR_DEFAULT_VALUE,
    ALL_DEVICES_ATTR_NAME,
    DOMAIN,
    LOGGER,
    SERVICE_CHANGE_BUTTON_STATE,
    SERVICE_RELOAD,
    TARGET_STATE_ATTR_DEFAULT_VALUE,
    TARGET_STATE_ATTR_NAME,
    ButtonType,
)
from .coordinator import (
    ShellyBlockCoordinator,
    ShellyEntryData,
    ShellyRpcCoordinator,
    get_entry_data,
    get_shelly_coordinator_from_entry_data,
)


async def async_setup_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Service handler setup."""

    def get_devices_to_change(
        shelly_devices: dict[str, ShellyEntryData],
        change_all_devices: bool,
        input_devices_to_change: list[str],
    ) -> list[ShellyBlockCoordinator | ShellyRpcCoordinator]:
        """Extract the shelly devices to change their button by the input data."""

        devices_to_change = []
        for shelly_device_entry_data in shelly_devices.values():
            shelly_device = get_shelly_coordinator_from_entry_data(
                shelly_device_entry_data
            )
            if shelly_device is not None and (
                change_all_devices or shelly_device.device_id in input_devices_to_change
            ):
                devices_to_change.append(shelly_device)

        return devices_to_change

    def handle_service_input(
        input_data: ReadOnlyDict
    ) -> tuple[ButtonType, bool, list[str]]:
        """Handle the input from user to values."""
        target_button_type_value = input_data.get(
            TARGET_STATE_ATTR_NAME, TARGET_STATE_ATTR_DEFAULT_VALUE
        )

        change_all_devices: bool = input_data.get(
            ALL_DEVICES_ATTR_NAME, ALL_DEVICES_ATTR_DEFAULT_VALUE
        )

        devices_to_change: list[str] = []
        if not change_all_devices:
            input_devices = cast(list[str], input_data.get("device_id"))
            devices_to_change.extend(input_devices)

        return (
            ButtonType[target_button_type_value],
            change_all_devices,
            devices_to_change,
        )

    def get_target_status(
        target_button_type: ButtonType, generation_number: int
    ) -> str:
        """get_target_status - by generation number."""
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

    async def change_button_type(
        shelly_device: ShellyBlockCoordinator | ShellyRpcCoordinator,
        target_button_type: ButtonType,
    ) -> bool:
        """Change the button type using RPC or REST."""

        LOGGER.debug(f"Changing button type to {shelly_device.name}")
        target_state = get_target_status(target_button_type, shelly_device.device.gen)
        await shelly_device.action_change_button(target_state)
        return True

    async def reload_service(call: ServiceCall) -> None:
        LOGGER.error(f"reload_service {str(call.data)}")

    async def change_button_state_service(call: ServiceCall) -> None:
        """Handle service call."""

        (
            target_button_type,
            change_all_devices,
            input_devices_to_change,
        ) = handle_service_input(call.data)

        shelly_devices: dict[str, ShellyEntryData] = get_entry_data(hass)

        LOGGER.debug(f"Shelly devices config entry keys : {shelly_devices.keys()}")

        devices_to_change = get_devices_to_change(
            shelly_devices, change_all_devices, input_devices_to_change
        )

        if len(devices_to_change) == 0:
            LOGGER.warning(f"Didn't find devices to change, the input {str(call.data)}")
            return

        for device_to_change in devices_to_change:
            await change_button_type(device_to_change, target_button_type)

        return

    hass.services.async_register(DOMAIN, SERVICE_RELOAD, reload_service)
    hass.services.async_register(
        DOMAIN, SERVICE_CHANGE_BUTTON_STATE, change_button_state_service
    )
