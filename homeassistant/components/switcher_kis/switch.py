"""Switcher integration Switch platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aioswitcher.api import Command, SwitcherBaseResponse, SwitcherType1Api, SwitcherType2Api
from aioswitcher.device import DeviceCategory, DeviceState, LightState
import voluptuous as vol

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitcherDataUpdateCoordinator
from .const import (
    CONF_AUTO_OFF,
    CONF_TIMER_MINUTES,
    SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_TURN_ON_WITH_TIMER_NAME,
    CONF_TOKEN,
    SIGNAL_DEVICE_ADD,
)

_LOGGER = logging.getLogger(__name__)

API_CONTROL_DEVICE = "control_device"
API_SET_LIGHT = "set_light"
LIGHT1_ID = "light"
LIGHT2_ID = "light2"

SERVICE_SET_AUTO_OFF_SCHEMA = {
    vol.Required(CONF_AUTO_OFF): cv.time_period_str,
}

SERVICE_TURN_ON_WITH_TIMER_SCHEMA = {
    vol.Required(CONF_TIMER_MINUTES): vol.All(
        cv.positive_int, vol.Range(min=1, max=150)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switcher switch from config entry."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_AUTO_OFF_NAME,
        SERVICE_SET_AUTO_OFF_SCHEMA,
        "async_set_auto_off_service",
    )

    platform.async_register_entity_service(
        SERVICE_TURN_ON_WITH_TIMER_NAME,
        SERVICE_TURN_ON_WITH_TIMER_SCHEMA,
        "async_turn_on_with_timer_service",
    )

    @callback
    def async_add_switch(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add switch from Switcher device."""
        if coordinator.data.device_type.category == DeviceCategory.POWER_PLUG:
            async_add_entities([SwitcherPowerPlugSwitchEntity(coordinator)])
        elif coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            async_add_entities([SwitcherWaterHeaterSwitchEntity(coordinator)])
        elif coordinator.data.device_type.category == DeviceCategory.SHUTTER_SINGLE_LIGHT_DUAL:
            async_add_entities([SwitcherShutterSingleLightDualSwitchEntity(coordinator, LIGHT1_ID), SwitcherShutterSingleLightDualSwitchEntity(coordinator, LIGHT2_ID)])
        elif coordinator.data.device_type.category == DeviceCategory.SHUTTER_DUAL_LIGHT_SINGLE:
            async_add_entities([SwitcherShutterDualLightSingleSwitchEntity(coordinator, LIGHT1_ID)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_switch)
    )


class SwitcherBaseSwitchEntity(
    CoordinatorEntity[SwitcherDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Switcher switch entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.control_result: bool | None = None

        # Entity class attributes
        self._attr_unique_id = f"{coordinator.device_id}-{coordinator.mac_address}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        self.async_write_ha_state()

    async def _async_call_api(self, api: str, *args: Any) -> None:
        """Call Switcher API."""
        _LOGGER.debug("Calling api for %s, api: '%s', args: %s", self.name, api, args)
        response: SwitcherBaseResponse = None
        error = None

        try:
            async with SwitcherType1Api(
                self.coordinator.data.device_type, self.coordinator.data.ip_address, self.coordinator.data.device_id
            ) as swapi:
                response = await getattr(swapi, api)(*args)
        except (asyncio.TimeoutError, OSError, RuntimeError) as err:
            error = repr(err)

        if error or not response or not response.successful:
            _LOGGER.error(
                "Call api for %s failed, api: '%s', args: %s, response/error: %s",
                self.coordinator.name,
                api,
                args,
                response or error,
            )
            self.coordinator.last_update_success = False

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.control_result is not None:
            return self.control_result

        return bool(self.coordinator.data.device_state == DeviceState.ON)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.ON)
        self.control_result = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.OFF)
        self.control_result = False
        self.async_write_ha_state()

    async def async_set_auto_off_service(self, auto_off: timedelta) -> None:
        """Use for handling setting device auto-off service calls."""
        _LOGGER.warning(
            "Service '%s' is not supported by %s",
            SERVICE_SET_AUTO_OFF_NAME,
            self.coordinator.name,
        )

    async def async_turn_on_with_timer_service(self, timer_minutes: int) -> None:
        """Use for turning device on with a timer service calls."""
        _LOGGER.warning(
            "Service '%s' is not supported by %s",
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            self.coordinator.name,
        )

class SwitcherBaselLightEntity(
    CoordinatorEntity[SwitcherDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Switcher light entity."""

    _attr_has_entity_name = True

    @property
    def name(self):
        """Name of the entity."""
        return self.light_id.capitalize()

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator, light_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.control_result: bool | None = None
        self.light_id = light_id

        # Entity class attributes
        self._attr_unique_id = f"{coordinator.device_id}-{coordinator.mac_address}-{self.light_id}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        self.async_write_ha_state()

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
            _LOGGER.error(
                "Call api for %s failed, api: '%s', args: %s, response/error: %s",
                self.name,
                api,
                args,
                response or error,
            )
            self.coordinator.last_update_success = False

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.control_result is not None:
            return self.control_result

        if self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_SINGLE_LIGHT_DUAL:
            if self.light_id == LIGHT1_ID:
                return bool(self.coordinator.data.light == LightState.ON)
            else:
                return bool(self.coordinator.data.light2 == LightState.ON)

        if self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_DUAL_LIGHT_SINGLE:
            if self.light_id == LIGHT1_ID:
                return bool(self.coordinator.data.light == LightState.ON)

        return bool(self.coordinator.data.device_state == LightState.ON)

    # This function return the currect light index (based of device type) used for the API Call
    def _get_light_index(self) -> int:
        if self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_SINGLE_LIGHT_DUAL:
            if self.light_id == LIGHT1_ID:
                return 1
            else:
                return 2
        elif self.coordinator.data.device_type.category == DeviceCategory.SHUTTER_DUAL_LIGHT_SINGLE:
            return 1
        return 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        index = self._get_light_index()
        await self._async_call_api(API_SET_LIGHT, LightState.ON, index)
        self.control_result = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        index = self._get_light_index()
        await self._async_call_api(API_SET_LIGHT, LightState.OFF, index)
        self.control_result = False
        self.async_write_ha_state()

class SwitcherPowerPlugSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher power plug switch entity."""

    _attr_device_class = SwitchDeviceClass.OUTLET


class SwitcherWaterHeaterSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher water heater switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    async def async_set_auto_off_service(self, auto_off: timedelta) -> None:
        """Use for handling setting device auto-off service calls."""
        await self._async_call_api("set_auto_shutdown", auto_off)
        self.async_write_ha_state()

    async def async_turn_on_with_timer_service(self, timer_minutes: int) -> None:
        """Use for turning device on with a timer service calls."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.ON, timer_minutes)
        self.control_result = True
        self.async_write_ha_state()

class SwitcherShutterSingleLightDualSwitchEntity(SwitcherBaselLightEntity):
    """Representation of a Switcher shutter single light dual switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

class SwitcherShutterDualLightSingleSwitchEntity(SwitcherBaselLightEntity):
    """Representation of a Switcher shutter dual light single switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
