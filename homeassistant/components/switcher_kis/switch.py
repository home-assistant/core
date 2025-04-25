"""Switcher integration Switch platform."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from aioswitcher.api import Command
from aioswitcher.device import (
    DeviceCategory,
    DeviceState,
    ShutterChildLock,
    SwitcherShutter,
)
import voluptuous as vol

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_AUTO_OFF,
    CONF_TIMER_MINUTES,
    SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_TURN_ON_WITH_TIMER_NAME,
    SIGNAL_DEVICE_ADD,
)
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity

_LOGGER = logging.getLogger(__name__)

API_CONTROL_DEVICE = "control_device"
API_SET_AUTO_SHUTDOWN = "set_auto_shutdown"
API_SET_CHILD_LOCK = "set_shutter_child_lock"

SERVICE_SET_AUTO_OFF_SCHEMA: VolDictType = {
    vol.Required(CONF_AUTO_OFF): cv.time_period_str,
}

SERVICE_TURN_ON_WITH_TIMER_SCHEMA: VolDictType = {
    vol.Required(CONF_TIMER_MINUTES): vol.All(
        cv.positive_int, vol.Range(min=1, max=150)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        entities: list[SwitchEntity] = []

        if coordinator.data.device_type.category == DeviceCategory.POWER_PLUG:
            entities.append(SwitcherPowerPlugSwitchEntity(coordinator))
        elif coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            entities.append(SwitcherWaterHeaterSwitchEntity(coordinator))
        elif coordinator.data.device_type.category in (
            DeviceCategory.SHUTTER,
            DeviceCategory.SINGLE_SHUTTER_DUAL_LIGHT,
            DeviceCategory.DUAL_SHUTTER_SINGLE_LIGHT,
        ):
            number_of_covers = len(cast(SwitcherShutter, coordinator.data).position)
            if number_of_covers == 1:
                entities.append(
                    SwitcherShutterChildLockSingleSwitchEntity(coordinator, 0)
                )
            else:
                entities.extend(
                    SwitcherShutterChildLockMultiSwitchEntity(coordinator, i)
                    for i in range(number_of_covers)
                )
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_switch)
    )


class SwitcherBaseSwitchEntity(SwitcherEntity, SwitchEntity):
    """Representation of a Switcher switch entity."""

    _attr_name = None

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.control_result: bool | None = None

        # Entity class attributes
        self._attr_unique_id = f"{coordinator.device_id}-{coordinator.mac_address}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        self.async_write_ha_state()

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


class SwitcherPowerPlugSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher power plug switch entity."""

    _attr_device_class = SwitchDeviceClass.OUTLET


class SwitcherWaterHeaterSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher water heater switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    async def async_set_auto_off_service(self, auto_off: timedelta) -> None:
        """Use for handling setting device auto-off service calls."""
        await self._async_call_api(API_SET_AUTO_SHUTDOWN, auto_off)
        self.async_write_ha_state()

    async def async_turn_on_with_timer_service(self, timer_minutes: int) -> None:
        """Use for turning device on with a timer service calls."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.ON, timer_minutes)
        self.control_result = True
        self.async_write_ha_state()


class SwitcherShutterChildLockBaseSwitchEntity(SwitcherEntity, SwitchEntity):
    """Representation of a Switcher shutter base switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lock-open"
    _cover_id: int

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.control_result: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.control_result is not None:
            return self.control_result

        data = cast(SwitcherShutter, self.coordinator.data)
        return bool(data.child_lock[self._cover_id] == ShutterChildLock.ON)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_call_api(
            API_SET_CHILD_LOCK, ShutterChildLock.ON, self._cover_id
        )
        self.control_result = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_call_api(
            API_SET_CHILD_LOCK, ShutterChildLock.OFF, self._cover_id
        )
        self.control_result = False
        self.async_write_ha_state()


class SwitcherShutterChildLockSingleSwitchEntity(
    SwitcherShutterChildLockBaseSwitchEntity
):
    """Representation of a Switcher runner child lock single switch entity."""

    _attr_translation_key = "child_lock"

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        cover_id: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._cover_id = cover_id

        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-child_lock"
        )


class SwitcherShutterChildLockMultiSwitchEntity(
    SwitcherShutterChildLockBaseSwitchEntity
):
    """Representation of a Switcher runner child lock multiple switch entity."""

    _attr_translation_key = "multi_child_lock"

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        cover_id: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._cover_id = cover_id

        self._attr_translation_placeholders = {"cover_id": str(cover_id + 1)}
        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{cover_id}-child_lock"
        )
