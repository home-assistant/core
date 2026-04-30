"""Switcher integration Switch platform."""

from __future__ import annotations

from datetime import time, timedelta
from typing import Any, cast

from aioswitcher.api import Command
from aioswitcher.api.messages import SwitcherGetSchedulesResponse
from aioswitcher.device import (
    DeviceCategory,
    DeviceState,
    ShutterChildLock,
    SwitcherShutter,
)
from aioswitcher.schedule import Days
import voluptuous as vol

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import (
    HomeAssistant,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import SwitcherConfigEntry
from .const import (
    CONF_AUTO_OFF,
    CONF_SCHEDULE_DAYS,
    CONF_SCHEDULE_END_TIME,
    CONF_SCHEDULE_ID,
    CONF_SCHEDULE_START_TIME,
    CONF_TIMER_MINUTES,
    DOMAIN,
    SERVICE_CREATE_SCHEDULE_NAME,
    SERVICE_DELETE_SCHEDULE_NAME,
    SERVICE_GET_SCHEDULES_NAME,
    SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_TURN_ON_WITH_TIMER_NAME,
    SIGNAL_DEVICE_ADD,
    SwitcherEntityFeature,
)
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity

PARALLEL_UPDATES = 1

API_CONTROL_DEVICE = "control_device"
API_SET_AUTO_SHUTDOWN = "set_auto_shutdown"
API_SET_CHILD_LOCK = "set_shutter_child_lock"
API_GET_SCHEDULES = "get_schedules"
API_CREATE_SCHEDULE = "create_schedule"
API_DELETE_SCHEDULE = "delete_schedule"

SERVICE_SET_AUTO_OFF_SCHEMA: VolDictType = {
    vol.Required(CONF_AUTO_OFF): cv.time_period_str,
}

SERVICE_TURN_ON_WITH_TIMER_SCHEMA: VolDictType = {
    vol.Required(CONF_TIMER_MINUTES): vol.All(
        cv.positive_int, vol.Range(min=1, max=150)
    ),
}

DAYS_MAPPING: dict[str, Days] = {
    "monday": Days.MONDAY,
    "tuesday": Days.TUESDAY,
    "wednesday": Days.WEDNESDAY,
    "thursday": Days.THURSDAY,
    "friday": Days.FRIDAY,
    "saturday": Days.SATURDAY,
    "sunday": Days.SUNDAY,
}

SERVICE_CREATE_SCHEDULE_SCHEMA: VolDictType = {
    vol.Required(CONF_SCHEDULE_START_TIME): cv.time,
    vol.Required(CONF_SCHEDULE_END_TIME): cv.time,
    vol.Optional(CONF_SCHEDULE_DAYS, default=[]): vol.All(
        cv.ensure_list, [vol.In(DAYS_MAPPING)]
    ),
}

SERVICE_DELETE_SCHEDULE_SCHEMA: VolDictType = {
    vol.Required(CONF_SCHEDULE_ID): vol.All(str, vol.In([str(i) for i in range(8)])),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitcherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switcher switch from config entry."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_AUTO_OFF_NAME,
        SERVICE_SET_AUTO_OFF_SCHEMA,
        "async_set_auto_off_service",
        entity_device_classes=(SwitchDeviceClass.SWITCH,),
    )

    platform.async_register_entity_service(
        SERVICE_TURN_ON_WITH_TIMER_NAME,
        SERVICE_TURN_ON_WITH_TIMER_SCHEMA,
        "async_turn_on_with_timer_service",
        entity_device_classes=(SwitchDeviceClass.SWITCH,),
    )

    platform.async_register_entity_service(
        SERVICE_GET_SCHEDULES_NAME,
        {},
        "async_get_schedules_service",
        required_features=[SwitcherEntityFeature.SCHEDULES],
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        SERVICE_CREATE_SCHEDULE_NAME,
        SERVICE_CREATE_SCHEDULE_SCHEMA,
        "async_create_schedule_service",
        required_features=[SwitcherEntityFeature.SCHEDULES],
    )

    platform.async_register_entity_service(
        SERVICE_DELETE_SCHEDULE_NAME,
        SERVICE_DELETE_SCHEDULE_SCHEMA,
        "async_delete_schedule_service",
        required_features=[SwitcherEntityFeature.SCHEDULES],
    )

    @callback
    def async_add_switch(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add switch from Switcher device."""
        entities: list[SwitchEntity] = []

        if coordinator.data.device_type.category == DeviceCategory.POWER_PLUG:
            entities.append(SwitcherPowerPlugSwitchEntity(coordinator))
        elif coordinator.data.device_type.category in [
            DeviceCategory.WATER_HEATER,
            DeviceCategory.HEATER,
        ]:
            entities.append(SwitcherHeaterSwitchEntity(coordinator))
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
        self._attr_unique_id = f"{coordinator.device_id}-{coordinator.mac_address}"
        self._update_data()

    def _update_data(self) -> None:
        """Update data from device."""
        if self.control_result is not None:
            self._attr_is_on = self.control_result
            self.control_result = None
            return

        self._attr_is_on = bool(self.coordinator.data.device_state == DeviceState.ON)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.ON)
        self._attr_is_on = self.control_result = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.OFF)
        self._attr_is_on = self.control_result = False
        self.async_write_ha_state()


class SwitcherPowerPlugSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher power plug switch entity."""

    _attr_device_class = SwitchDeviceClass.OUTLET


class SwitcherHeaterSwitchEntity(SwitcherBaseSwitchEntity):
    """Representation of a Switcher heater switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        if coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            self._attr_supported_features = SwitcherEntityFeature.SCHEDULES

    async def async_set_auto_off_service(self, auto_off: timedelta) -> None:
        """Use for handling setting device auto-off service calls."""
        await self._async_call_api(API_SET_AUTO_SHUTDOWN, auto_off)
        self.async_write_ha_state()

    async def async_turn_on_with_timer_service(self, timer_minutes: int) -> None:
        """Use for turning device on with a timer service calls."""
        await self._async_call_api(API_CONTROL_DEVICE, Command.ON, timer_minutes)
        self._attr_is_on = self.control_result = True
        self.async_write_ha_state()

    async def async_get_schedules_service(self) -> ServiceResponse:
        """Return all schedules configured on the device."""
        response = cast(
            SwitcherGetSchedulesResponse,
            await self._async_call_api(API_GET_SCHEDULES),
        )
        return {
            "schedules": [
                {
                    "schedule_id": s.schedule_id,
                    "recurring": s.recurring,
                    "days": [
                        d.name.lower() for d in sorted(s.days, key=lambda d: d.name)
                    ],
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration,
                }
                for s in sorted(response.schedules, key=lambda s: s.schedule_id)
            ]
        }

    async def async_create_schedule_service(
        self, start_time: time, end_time: time, days: list[str]
    ) -> None:
        """Create a new schedule on the device."""
        if end_time <= start_time:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schedule_end_time_not_after_start_time",
            )
        await self._async_call_api(
            API_CREATE_SCHEDULE,
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            {DAYS_MAPPING[d] for d in days},
        )

    async def async_delete_schedule_service(self, schedule_id: str) -> None:
        """Delete a schedule from the device by its ID."""
        await self._async_call_api(API_DELETE_SCHEDULE, schedule_id)


class SwitcherShutterChildLockBaseSwitchEntity(SwitcherEntity, SwitchEntity):
    """Representation of a Switcher child lock base switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lock-open"
    _cover_id: int

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        cover_id: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._cover_id = cover_id
        self.control_result: bool | None = None
        self._update_data()

    def _update_data(self) -> None:
        """Update data from device."""
        if self.control_result is not None:
            self._attr_is_on = self.control_result
            self.control_result = None
            return

        data = cast(SwitcherShutter, self.coordinator.data)
        self._attr_is_on = bool(data.child_lock[self._cover_id] == ShutterChildLock.ON)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_call_api(
            API_SET_CHILD_LOCK, ShutterChildLock.ON, self._cover_id
        )
        self._attr_is_on = self.control_result = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_call_api(
            API_SET_CHILD_LOCK, ShutterChildLock.OFF, self._cover_id
        )
        self._attr_is_on = self.control_result = False
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
        super().__init__(coordinator, cover_id)
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
        super().__init__(coordinator, cover_id)

        self._attr_translation_placeholders = {"cover_id": str(cover_id + 1)}
        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{cover_id}-child_lock"
        )
