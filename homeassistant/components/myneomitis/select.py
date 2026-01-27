"""Select entities for MyNeomitis integration.

This module defines and sets up the select entities for the MyNeomitis integration.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pyaxencoapi import PyAxencoAPI

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyNeomitisConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MODELES = ["EWS"]
SUB_MODELES = ["UFH"]

PRESET_MODE_MAP = {
    "comfort": 1,
    "eco": 2,
    "antifrost": 3,
    "standby": 4,
    "boost": 6,
    "setpoint": 8,
    "comfort_plus": 20,
    "eco_1": 40,
    "eco_2": 41,
    "auto": 60,
}

PRESET_MODE_MAP_RELAIS = {
    "on": 1,
    "off": 2,
    "auto": 60,
}

PRESET_MODE_MAP_UFH = {
    "heating": 0,
    "cooling": 1,
}

REVERSE_PRESET_MODE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

REVERSE_PRESET_MODE_MAP_RELAIS = {v: k for k, v in PRESET_MODE_MAP_RELAIS.items()}

REVERSE_PRESET_MODE_MAP_UFH = {v: k for k, v in PRESET_MODE_MAP_UFH.items()}


@dataclass(frozen=True, kw_only=True)
class MyNeoSelectEntityDescription(SelectEntityDescription):
    """Describe MyNeomitis select entity."""

    preset_mode_map: dict[str, int]
    reverse_preset_mode_map: dict[int, str]
    state_key: str


SELECT_TYPES: dict[str, MyNeoSelectEntityDescription] = {
    "relais": MyNeoSelectEntityDescription(
        key="relais",
        translation_key="relais",
        options=list(PRESET_MODE_MAP_RELAIS),
        preset_mode_map=PRESET_MODE_MAP_RELAIS,
        reverse_preset_mode_map=REVERSE_PRESET_MODE_MAP_RELAIS,
        state_key="targetMode",
    ),
    "pilote": MyNeoSelectEntityDescription(
        key="pilote",
        translation_key="pilote",
        options=list(PRESET_MODE_MAP),
        preset_mode_map=PRESET_MODE_MAP,
        reverse_preset_mode_map=REVERSE_PRESET_MODE_MAP,
        state_key="targetMode",
    ),
    "UFH": MyNeoSelectEntityDescription(
        key="ufh",
        translation_key="ufh",
        options=list(PRESET_MODE_MAP_UFH),
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
    """Set up Select entities from a config entry."""
    api = config_entry.runtime_data.api
    devices = config_entry.runtime_data.devices

    def _create_entity(device: dict) -> MyNeoSelect:
        """Create a select entity for a device."""
        if device["model"] == "EWS":
            # Check if device has relayMode to determine if it's a relais or pilote
            if "relayMode" in device.get("state", {}):
                description = SELECT_TYPES["relais"]
            else:
                description = SELECT_TYPES["pilote"]
        else:  # UFH
            description = SELECT_TYPES["UFH"]

        return MyNeoSelect(api, device, description)

    select_entities = [
        _create_entity(device)
        for device in devices
        if device["model"] in MODELES or device["model"] in SUB_MODELES
    ]

    async_add_entities(select_entities)


class MyNeoSelect(SelectEntity):
    """Select entity for MyNeomitis devices."""

    entity_description: MyNeoSelectEntityDescription
    _attr_has_entity_name = True
    _attr_name = None  # Entity represents the device itself

    def __init__(
        self,
        api: PyAxencoAPI,
        device: dict[str, Any],
        description: MyNeoSelectEntityDescription,
    ) -> None:
        """Initialize the MyNeoSelect entity."""
        self.entity_description = description
        self._api = api
        self._device = device
        self._attr_unique_id = device["_id"]
        self._attr_available = device["connected"]
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device["_id"])},
            name=device["name"],
            manufacturer="Axenco",
            model=device["model"],
        )
        # Set current option based on device state
        current_mode = device.get("state", {}).get(description.state_key)
        self._attr_current_option = description.reverse_preset_mode_map.get(
            current_mode
        )

        self._program = device.get("program", {}).get("data", {})

    async def async_added_to_hass(self) -> None:
        """Register listener when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._api.register_listener(self._device["_id"], self.handle_ws_update)
        )

    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        """Handle WebSocket updates for the device."""
        if not new_state:
            return

        if "connected" in new_state:
            self._attr_available = new_state["connected"]

        if "program" in new_state:
            new_data = new_state["program"].get("data", {})
            self._program.update(new_data)

        # Check for state updates using the description's state_key
        state_key = self.entity_description.state_key
        if state_key in new_state:
            mode = new_state.get(state_key)
            if mode is not None:
                self._attr_current_option = (
                    self.entity_description.reverse_preset_mode_map.get(mode)
                )

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Send the new mode via the API."""
        mode_code = self.entity_description.preset_mode_map.get(option)

        if mode_code is None:
            _LOGGER.warning("MyNeomitis : Unknown mode selected: %s", option)
            return

        await self._api.set_device_mode(self._device["_id"], mode_code)
        self._attr_current_option = option
        self.async_write_ha_state()
