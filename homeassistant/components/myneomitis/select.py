"""Select entities for MyNeomitis integration.

This module defines and sets up the select entities for the MyNeomitis integration.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pyaxencoapi import PyAxencoAPI

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyNeomitisConfigEntry
from .logger import log_ws_update
from .utils import (
    PRESET_MODE_MAP,
    PRESET_MODE_MAP_RELAIS,
    PRESET_MODE_MAP_UFH,
    REVERSE_PRESET_MODE_MAP,
    REVERSE_PRESET_MODE_MAP_RELAIS,
    REVERSE_PRESET_MODE_MAP_UFH,
    get_device_by_rfid,
    parents_to_dict,
)

_LOGGER = logging.getLogger(__name__)

MODELES = ["EWS"]
SUB_MODELES = ["UFH"]

PRESET_OPTIONS = {
    "relais": ["on", "off", "auto"],
    "pilote": [
        "boost",
        "auto",
        "comfort",
        "eco_2",
        "eco_1",
        "eco",
        "antifrost",
        "standby",
    ],
    "UFH": ["cooling", "heating"],
}


@dataclass(frozen=True, kw_only=True)
class MyNeoSelectEntityDescription(SelectEntityDescription):
    """Describe MyNeomitis select entity."""

    preset_mode_map: dict[str, int]
    reverse_preset_mode_map: dict[int, str]
    state_key: str


SELECT_TYPES: dict[str, MyNeoSelectEntityDescription] = {
    "relais": MyNeoSelectEntityDescription(
        key="relais",
        translation_key="select_myneomitis",
        options=PRESET_OPTIONS["relais"],
        preset_mode_map=PRESET_MODE_MAP_RELAIS,
        reverse_preset_mode_map=REVERSE_PRESET_MODE_MAP_RELAIS,
        state_key="targetMode",
    ),
    "pilote": MyNeoSelectEntityDescription(
        key="pilote",
        translation_key="select_myneomitis",
        options=PRESET_OPTIONS["pilote"],
        preset_mode_map=PRESET_MODE_MAP,
        reverse_preset_mode_map=REVERSE_PRESET_MODE_MAP,
        state_key="targetMode",
    ),
    "UFH": MyNeoSelectEntityDescription(
        key="UFH",
        translation_key="select_myneomitis",
        options=PRESET_OPTIONS["UFH"],
        preset_mode_map=PRESET_MODE_MAP_UFH,
        reverse_preset_mode_map=REVERSE_PRESET_MODE_MAP_UFH,
        state_key="changeOverUser",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyNeomitisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Select entities from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (MyNeomitisConfigEntry): The configuration entry.
        async_add_entities (AddEntitiesCallback): Callback to add entities.

    """
    api = config_entry.runtime_data.api
    devices = config_entry.runtime_data.devices
    added_ids = set()
    entities_by_id: dict[str, MyNeoSelect] = {}

    def _get_entity_description(device: dict) -> MyNeoSelectEntityDescription | None:
        """Determine the appropriate entity description for a device."""
        if device["model"] == "EWS":
            # Check if device has relayMode to determine if it's a relais or pilote
            if "relayMode" in device.get("state", {}):
                return SELECT_TYPES["relais"]
            return SELECT_TYPES["pilote"]
        if device["model"] == "UFH":
            return SELECT_TYPES["UFH"]
        return None

    def _create_entity(device: dict) -> MyNeoSelect | None:
        """Create a select entity for a device.

        Args:
            device: The device data dictionary.

        Returns:
            A MyNeoSelect entity or None if the device is not supported.

        """
        description = _get_entity_description(device)
        if description is None:
            return None
        entity = MyNeoSelect(api, device, [*devices, device], description)
        added_ids.add(device["_id"])
        entities_by_id[f"myneo_{device['_id']}"] = entity
        return entity

    select_entities = [
        entity
        for device in devices
        if device["model"] in MODELES or device["model"] in SUB_MODELES
        if (entity := _create_entity(device)) is not None
    ]

    async_add_entities(select_entities)

    async def add_new_entity(device: dict) -> None:
        """Add a new select entity dynamically when a device is discovered."""
        if device["_id"] in added_ids:
            return
        if device["model"] not in MODELES and device["model"] not in SUB_MODELES:
            return
        entity = _create_entity(device)
        if entity is None:
            return
        _LOGGER.info("MyNeomitis : Adding new select entity: %s", entity.name)
        async_add_entities([entity])

    async def remove_entity(device_id: str) -> None:
        """Remove a select entity dynamically when a device is removed."""
        uid = f"myneo_{device_id}"
        entity = entities_by_id.get(uid)
        if entity:
            _LOGGER.info("MyNeomitis : Removing select entity: %s", uid)
            await entity.async_remove()
            added_ids.discard(device_id)
            entities_by_id.pop(uid, None)

    api.register_discovery_callback(
        lambda dev: hass.async_create_task(add_new_entity(dev))
    )
    api.register_removal_callback(
        lambda dev_id: hass.async_create_task(remove_entity(dev_id))
    )


class MyNeoSelect(SelectEntity):
    """Select entity for MyNeomitis devices."""

    entity_description: MyNeoSelectEntityDescription

    def __init__(
        self,
        api: PyAxencoAPI,
        device: dict[str, Any],
        devices: list[dict[str, Any]],
        description: MyNeoSelectEntityDescription,
    ) -> None:
        """Initialize the MyNeoSelect entity.

        Args:
            api: The API instance to communicate with the device.
            device: The device data dictionary.
            devices: A list of all devices managed by the integration.
            description: The entity description for this select entity.

        """
        super().__init__()
        self.entity_description = description
        self._api = api
        self._device = device
        self._attr_name = f"MyNeo {device['name']}"
        self._attr_unique_id = f"myneo_{device['_id']}"
        self._attr_available = device["connected"]
        self._parents = (
            parents_to_dict(device["parents"]) if "parents" in device else {}
        )
        self._primary_parent = (
            get_device_by_rfid(devices, self._parents.get("primary") or "")
            if "primary" in self._parents
            else {}
        )
        self._is_sub_device = device["model"] in SUB_MODELES

        # Set current option based on device state
        current_mode = device.get("state", {}).get(description.state_key)
        self._attr_current_option = description.reverse_preset_mode_map.get(
            current_mode, STATE_UNKNOWN
        )

        self._program = device.get("program", {}).get("data", {})

        api.register_listener(device["_id"], self.handle_ws_update)

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._attr_current_option in {"off", "standby"}:
            return "mdi:toggle-switch-off-outline"
        if self._attr_current_option in {"eco", "eco_1", "eco_2"}:
            return "mdi:leaf"
        if self._attr_current_option in {"comfort", "heating"}:
            return "mdi:fire"
        if self._attr_current_option in {"antifrost", "cooling"}:
            return "mdi:snowflake"
        if self._attr_current_option == "boost":
            return "mdi:rocket-launch"
        if self._attr_current_option == "auto":
            return "mdi:refresh-auto"
        return "mdi:toggle-switch"

    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        """Handle WebSocket updates for the device.

        Args:
            new_state: The new state data received from the WebSocket.

        """
        state = new_state
        if not state:
            return

        if "connected" in state:
            self._attr_available = state["connected"]

        if "program" in state:
            new_data = state["program"].get("data", {})
            self._program.update(new_data)

        if "name" in state:
            self._attr_name = state["name"]

        # Check for state updates using the description's state_key
        state_key = self.entity_description.state_key
        if state_key in state:
            mode = state.get(state_key)
            if mode is not None:
                self._attr_current_option = (
                    self.entity_description.reverse_preset_mode_map.get(
                        mode, STATE_UNKNOWN
                    )
                )
                log_ws_update(str(self._attr_name), state)

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Send the new mode via the API.

        Args:
            option: The selected option to set.

        """
        mode_code = self.entity_description.preset_mode_map.get(option)

        if mode_code is None:
            _LOGGER.warning("MyNeomitis : Unknown mode selected: %s", option)
            return

        await self.set_api_device_mode(option)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def set_api_device_mode(self, mode: str) -> Any:
        """Set the device mode.

        Args:
            mode: The desired mode to set for the device.

        Returns:
            The result of the API call to set the device mode.

        """
        mode_code = self.entity_description.preset_mode_map[mode]

        if self._is_sub_device:
            if self._device["model"] == "UFH":
                return await self._api.set_sub_device_mode_ufh(
                    self._parents["gateway"],
                    self._device["rfid"],
                    mode_code,
                )

            return await self._api.set_sub_device_mode(
                self._parents["gateway"],
                self._device["rfid"],
                mode_code,
            )
        return await self._api.set_device_mode(self._device["_id"], mode_code)
