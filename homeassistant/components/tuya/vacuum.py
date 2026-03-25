"""Support for Tuya Vacuums."""

from __future__ import annotations

from typing import Any

from tuya_device_handlers.definition.vacuum import (
    TuyaVacuumDefinition,
    get_default_definition,
)
from tuya_device_handlers.helpers.homeassistant import (
    TuyaVacuumAction,
    TuyaVacuumActivity,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory
from .entity import TuyaEntity

_TUYA_TO_HA_ACTIVITY_MAPPINGS = {
    TuyaVacuumActivity.CLEANING: VacuumActivity.CLEANING,
    TuyaVacuumActivity.DOCKED: VacuumActivity.DOCKED,
    TuyaVacuumActivity.IDLE: VacuumActivity.IDLE,
    TuyaVacuumActivity.PAUSED: VacuumActivity.PAUSED,
    TuyaVacuumActivity.RETURNING: VacuumActivity.RETURNING,
    TuyaVacuumActivity.ERROR: VacuumActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya vacuum."""
        entities: list[TuyaVacuumEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if device.category == DeviceCategory.SD:
                entities.append(
                    TuyaVacuumEntity(device, manager, get_default_definition(device))
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaVacuumEntity(TuyaEntity, StateVacuumEntity):
    """Tuya Vacuum Device."""

    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        definition: TuyaVacuumDefinition,
    ) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)
        self._action_wrapper = definition.action_wrapper
        self._activity_wrapper = definition.activity_wrapper
        self._fan_speed_wrapper = definition.fan_speed_wrapper

        self._attr_fan_speed_list = []
        self._attr_supported_features = VacuumEntityFeature.SEND_COMMAND

        if definition.action_wrapper:
            if TuyaVacuumAction.PAUSE in definition.action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.PAUSE
            if TuyaVacuumAction.RETURN_TO_BASE in definition.action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME
            if TuyaVacuumAction.LOCATE in definition.action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.LOCATE
            if TuyaVacuumAction.START in definition.action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.START
            if TuyaVacuumAction.STOP in definition.action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.STOP

        if definition.activity_wrapper:
            self._attr_supported_features |= VacuumEntityFeature.STATE

        if definition.fan_speed_wrapper:
            self._attr_fan_speed_list = definition.fan_speed_wrapper.options
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._read_wrapper(self._fan_speed_wrapper)

    @property
    def activity(self) -> VacuumActivity | None:
        """Return Tuya vacuum device state."""
        tuya_value = self._read_wrapper(self._activity_wrapper)
        return _TUYA_TO_HA_ACTIVITY_MAPPINGS.get(tuya_value) if tuya_value else None

    async def async_start(self, **kwargs: Any) -> None:
        """Start the device."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaVacuumAction.START
        )

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaVacuumAction.STOP
        )

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaVacuumAction.PAUSE
        )

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaVacuumAction.RETURN_TO_BASE
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaVacuumAction.LOCATE
        )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self._async_send_wrapper_updates(self._fan_speed_wrapper, fan_speed)

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send raw command."""
        if not params:
            raise ValueError("Params cannot be omitted for Tuya vacuum commands")
        if not isinstance(params, list):
            raise TypeError("Params must be a list for Tuya vacuum commands")
        await self._async_send_commands([{"code": command, "value": params[0]}])
