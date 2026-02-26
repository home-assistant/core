"""Select entities for MyNeomitis integration.

This module defines and sets up the select entities for the MyNeomitis integration.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pyaxencoapi import PyAxencoAPI

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyNeomitisConfigEntry, process_connection_update
from .const import (
    DOMAIN,
    PRESET_MODE_MAP,
    PRESET_MODE_MAP_RELAIS,
    PRESET_MODE_MAP_UFH,
    PRESET_MODE_SELECT_EXTRAS,
    REVERSE_PRESET_MODE_MAP_RELAIS,
    REVERSE_PRESET_MODE_MAP_UFH,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_MODELS: frozenset[str] = frozenset({"EWS"})
SUPPORTED_SUB_MODELS: frozenset[str] = frozenset({"UFH"})

PILOTE_MODE_MAP: dict[str, int] = {**PRESET_MODE_MAP, **PRESET_MODE_SELECT_EXTRAS}
REVERSE_PILOTE_MODE_MAP: dict[int, str] = {v: k for k, v in PILOTE_MODE_MAP.items()}


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
        options=list(PILOTE_MODE_MAP),
        preset_mode_map=PILOTE_MODE_MAP,
        reverse_preset_mode_map=REVERSE_PILOTE_MODE_MAP,
        state_key="targetMode",
    ),
    "ufh": MyNeoSelectEntityDescription(
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
            if "relayMode" in device.get("state", {}):
                description = SELECT_TYPES["relais"]
            else:
                description = SELECT_TYPES["pilote"]
        else:  # UFH
            description = SELECT_TYPES["ufh"]

        return MyNeoSelect(api, device, description)

    select_entities: list[MyNeoSelect] = []
    for device in devices:
        model = device.get("model")
        if model not in SUPPORTED_MODELS | SUPPORTED_SUB_MODELS:
            continue

        device_id = device.get("_id")
        if not device_id:
            _LOGGER.warning(
                "Skipping MyNeomitis select device without _id: %s", device.get("name")
            )
            continue

        select_entities.append(_create_entity(device))

    if select_entities:
        async_add_entities(select_entities)


class MyNeoSelect(SelectEntity):
    """Select entity for MyNeomitis devices."""

    entity_description: MyNeoSelectEntityDescription
    _attr_has_entity_name = True
    _attr_name = None  # Entity represents the device itself
    _attr_should_poll = False

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
        device_id = device.get("_id")
        if not device_id:
            raise ValueError("Device is missing required _id")
        self._attr_unique_id = device_id
        self._device_id = device_id
        self._attr_available = bool(device.get("connected", False))
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("name") or device_id,
            manufacturer="Axenco",
            model=device.get("model", ""),
        )
        # Set current option based on device state
        current_mode = device.get("state", {}).get(description.state_key)
        self._attr_current_option = description.reverse_preset_mode_map.get(
            current_mode
        )
        self._unavailable_logged: bool = False

    async def async_added_to_hass(self) -> None:
        """Register listener when entity is added to hass."""
        await super().async_added_to_hass()
        register_listener = getattr(self._api, "register_listener", None)
        if not callable(register_listener):
            _LOGGER.debug(
                "API has no register_listener, skipping ws listener for %s",
                self._device_id,
            )
            return

        unsubscribe = register_listener(self._device_id, self.handle_ws_update)
        if callable(unsubscribe):
            self.async_on_remove(unsubscribe)
        elif hasattr(unsubscribe, "unsubscribe"):
            self.async_on_remove(unsubscribe.unsubscribe)
        elif hasattr(unsubscribe, "close"):
            self.async_on_remove(unsubscribe.close)
        elif unsubscribe is None:
            pass
        else:
            _LOGGER.debug(
                "register_listener returned unsupported type %s for %s",
                type(unsubscribe),
                self._device_id,
            )

    @callback
    def handle_ws_update(self, new_state: dict[str, Any]) -> None:
        """Handle WebSocket updates for the device."""

        available = process_connection_update(new_state)
        if available is not None:
            self._attr_available = available
            if not available:
                if not self._unavailable_logged:
                    _LOGGER.info("The entity %s is unavailable", self.entity_id)
                    self._unavailable_logged = True
            elif self._unavailable_logged:
                _LOGGER.info("The entity %s is back online", self.entity_id)
                self._unavailable_logged = False

        if not new_state:
            return

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
            _LOGGER.warning("Unknown mode selected: %s", option)
            return

        await self._api.set_device_mode(self._device["_id"], mode_code)
        self._attr_current_option = option
        self.async_write_ha_state()
