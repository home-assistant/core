"""Switcher integration Cover platform."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioswitcher.api import SwitcherBaseResponse, SwitcherType2Api
from aioswitcher.device import DeviceCategory, ShutterDirection, SwitcherShutter

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitcherDataUpdateCoordinator
from .const import CONF_TOKEN, SIGNAL_DEVICE_ADD

_LOGGER = logging.getLogger(__name__)

API_SET_POSITON = "set_position"
API_STOP = "stop_shutter"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switcher cover from config entry."""

    @callback
    def async_add_cover(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add cover from Switcher device."""
        if coordinator.data.device_type.category == DeviceCategory.SHUTTER:
            async_add_entities([SwitcherCoverEntity(coordinator)])
        elif coordinator.data.device_type.category == DeviceCategory.SHUTTER_SINGLE_LIGHT_DUAL:
            async_add_entities([SwitcherCoverEntity(coordinator)])
        elif coordinator.data.device_type.category == DeviceCategory.SHUTTER_DUAL_LIGHT_SINGLE:
            async_add_entities([SwitcherCoverEntity(coordinator)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_cover)
    )


class SwitcherCoverEntity(
    CoordinatorEntity[SwitcherDataUpdateCoordinator], CoverEntity
):
    """Representation of a Switcher cover entity."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_name = coordinator.name
        self._attr_unique_id = f"{coordinator.device_id}-{coordinator.mac_address}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )

        self._update_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_data()
        self.async_write_ha_state()

    def _update_data(self) -> None:
        """Update data from device."""
        data: SwitcherShutter = self.coordinator.data
        self._attr_current_cover_position = data.position
        self._attr_is_closed = data.position == 0
        self._attr_is_closing = data.direction == ShutterDirection.SHUTTER_DOWN
        self._attr_is_opening = data.direction == ShutterDirection.SHUTTER_UP

    async def _async_call_api(self, api: str, *args: Any) -> None:
        """Call Switcher API."""
        _LOGGER.debug("Calling api for %s, api: '%s', args: %s", self.name, api, args)
        response: SwitcherBaseResponse = None
        error = None

        try:
            async with SwitcherType2Api(
                self.coordinator.data.device_type, self.coordinator.data.ip_address, self.coordinator.data.device_id, self.coordinator.config_entry.data.get(CONF_TOKEN)
            ) as swapi:
                response = await getattr(swapi, api)(*args)
        except (asyncio.TimeoutError, OSError, RuntimeError) as err:
            error = repr(err)

        if error or not response or not response.successful:
            self.coordinator.last_update_success = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Call api for {self.name} failed, api: '{api}', "
                f"args: {args}, response/error: {response or error}"
            )

    def _get_shutter_index(self, is_first_shutter: bool = True) -> int:
        if self.coordinator.data.device_type.category == DeviceCategory.SHUTTER:
            return 1
        elif self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_SINGLE_LIGHT_DUAL:
            return 3
        elif self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_DUAL_LIGHT_SINGLE:
            if is_first_shutter:
                return 2
            else:
                return 3
        else:
            return 0

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        index = self._get_shutter_index()
        await self._async_call_api(API_SET_POSITON, 0, index)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        index = self._get_shutter_index()
        await self._async_call_api(API_SET_POSITON, 100, index)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        index = self._get_shutter_index()
        await self._async_call_api(API_SET_POSITON, kwargs[ATTR_POSITION], index)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        index = self._get_shutter_index()
        await self._async_call_api(API_STOP, index)

    async def async_close_cover2(self, **kwargs: Any) -> None:
        """Close cover 2."""
        index = self._get_shutter_index(False)
        await self._async_call_api(API_SET_POSITON, 0, index)

    async def async_open_cover2(self, **kwargs: Any) -> None:
        """Open cover 2."""
        index = self._get_shutter_index(False)
        await self._async_call_api(API_SET_POSITON, 100, index)

    async def async_set_cover2_position(self, **kwargs: Any) -> None:
        """Move the cover 2 to a specific position."""
        index = self._get_shutter_index(False)
        await self._async_call_api(API_SET_POSITON, kwargs[ATTR_POSITION], index)

    async def async_stop_cover2(self, **kwargs: Any) -> None:
        """Stop the cover 2."""
        index = self._get_shutter_index(False)
        await self._async_call_api(API_STOP, index)
