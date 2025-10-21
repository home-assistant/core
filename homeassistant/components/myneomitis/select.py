"""Select entities for MyNeomitis integration.

This module defines and sets up the select entities for the MyNeomitis integration.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .logger import log_ws_update_switch, log_ws_update_ufh
from .utils import (
    PRESET_MODE_MAP,
    PRESET_MODE_MAP_RELAIS,
    PRESET_MODE_MAP_UFH,
    REVERSE_PRESET_MODE_MAP,
    REVERSE_PRESET_MODE_MAP_RELAIS,
    REVERSE_PRESET_MODE_MAP_UFH,
    format_week_schedule,
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
        "eco-2",
        "eco-1",
        "eco",
        "antifrost",
        "standby",
    ],
    "UFH": ["cooling", "heating"],
}


class MyNeoSelect(SelectEntity):
    """Select entity for MyNeomitis devices."""

    def __init__(
        self, api: Any, device: dict[str, Any], devices: list[dict[str, Any]]
    ) -> None:
        """Initialize the MyNeoSelect entity.

        Args:
            api: The API instance to communicate with the device.
            device: The device data dictionary.
            devices: A list of all devices managed by the integration.

        """
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
        self._attr_translation_key = "select_myneomitis"

        if device["model"] == "EWS":
            self._type = (
                "relais" if "relayMode" in device.get("state", {}) else "pilote"
            )
            self._preset_mode_map = (
                PRESET_MODE_MAP_RELAIS if self._type == "relais" else PRESET_MODE_MAP
            )
            self._reverse_preset_mode_map = (
                REVERSE_PRESET_MODE_MAP_RELAIS
                if self._type == "relais"
                else REVERSE_PRESET_MODE_MAP
            )
            self._attr_options = PRESET_OPTIONS.get(self._type, [])
            self._attr_current_option = self._reverse_preset_mode_map.get(
                device.get("state", {}).get("targetMode"), STATE_UNKNOWN
            )

        elif device["model"] == "UFH":
            self._type = "UFH"
            self._preset_mode_map = PRESET_MODE_MAP_UFH
            self._reverse_preset_mode_map = REVERSE_PRESET_MODE_MAP_UFH
            self._attr_options = PRESET_OPTIONS.get(self._type, [])
            self._attr_current_option = self._reverse_preset_mode_map.get(
                device.get("state", {}).get("changeOverUser"), STATE_UNKNOWN
            )

        self._program = device.get("program", {}).get("data", {})

        api.register_listener(device["_id"], self.handle_ws_update)

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._attr_current_option in {"off", "standby"}:
            return "mdi:toggle-switch-off-outline"
        if self._attr_current_option in {"eco", "eco-1", "eco-2"}:
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

        if "changeOverUser" in state:
            mode = state.get("changeOverUser")
            if mode is not None:
                self._attr_current_option = self._reverse_preset_mode_map.get(
                    mode, STATE_UNKNOWN
                )
                log_ws_update_ufh(str(self._attr_name), state)

        if "targetMode" in state:
            mode = state.get("targetMode")
            if mode is not None:
                self._attr_current_option = self._reverse_preset_mode_map.get(
                    mode, STATE_UNKNOWN
                )
                log_ws_update_switch(str(self._attr_name), state)

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Show full week planning if available, and WebSocket status.
        """
        attributes = {
            "ws_status": "connected" if self._api.sio.connected else "disconnected",
            "is_connected": "True" if self._attr_available else "False",
        }

        if self._program:
            week_planning = format_week_schedule(
                self._program, isRelais=(self._type == "relais")
            )
            for day, planning in week_planning.items():
                attributes[f"planning_{day.lower()}"] = planning

        return attributes

    async def async_select_option(self, option: str) -> None:
        """Send the new mode via the API.

        Args:
            option: The selected option to set.

        """
        mode_code = self._preset_mode_map.get(option)

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
        if self._is_sub_device:
            if self._device["model"] == "UFH":
                return await self._api.set_sub_device_mode_ufh(
                    self._parents["gateway"],
                    self._device["rfid"],
                    self._preset_mode_map[mode],
                )

            return await self._api.set_sub_device_mode(
                self._parents["gateway"],
                self._device["rfid"],
                self._preset_mode_map[mode],
            )
        return await self._api.set_device_mode(
            self._device["_id"], self._preset_mode_map[mode]
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Select entities from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The configuration entry.
        async_add_entities (AddEntitiesCallback): Callback to add entities.

    """
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    api = entry_data["api"]
    devices = entry_data["devices"]
    added_ids = set()
    entities_by_id: dict[str, MyNeoSelect] = {}

    def _create_entity(device: dict) -> MyNeoSelect:
        entity = MyNeoSelect(api, device, [*devices, device])
        added_ids.add(device["_id"])
        entities_by_id[f"myneo_{device['_id']}"] = entity
        return entity

    select_entities = [
        _create_entity(device)
        for device in devices
        if device["model"] in MODELES or device["model"] in SUB_MODELES
    ]

    async_add_entities(select_entities)

    async def add_new_entity(device: dict) -> None:
        if device["_id"] in added_ids:
            return
        if device["model"] not in MODELES and device["model"] not in SUB_MODELES:
            return
        entity = _create_entity(device)
        _LOGGER.info("MyNeomitis : Adding new select entity: %s", entity.name)
        async_add_entities([entity])

    async def remove_entity(device_id: str) -> None:
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
