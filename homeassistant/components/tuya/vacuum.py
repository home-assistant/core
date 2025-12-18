"""Support for Tuya Vacuums."""

from __future__ import annotations

from typing import Any

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
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBooleanWrapper, DPCodeEnumWrapper

TUYA_MODE_RETURN_HOME = "chargego"
TUYA_STATUS_TO_HA = {
    "charge_done": VacuumActivity.DOCKED,
    "chargecompleted": VacuumActivity.DOCKED,
    "chargego": VacuumActivity.DOCKED,
    "charging": VacuumActivity.DOCKED,
    "cleaning": VacuumActivity.CLEANING,
    "docking": VacuumActivity.RETURNING,
    "goto_charge": VacuumActivity.RETURNING,
    "goto_pos": VacuumActivity.CLEANING,
    "mop_clean": VacuumActivity.CLEANING,
    "part_clean": VacuumActivity.CLEANING,
    "paused": VacuumActivity.PAUSED,
    "pick_zone_clean": VacuumActivity.CLEANING,
    "pos_arrived": VacuumActivity.CLEANING,
    "pos_unarrive": VacuumActivity.CLEANING,
    "random": VacuumActivity.CLEANING,
    "sleep": VacuumActivity.IDLE,
    "smart_clean": VacuumActivity.CLEANING,
    "smart": VacuumActivity.CLEANING,
    "spot_clean": VacuumActivity.CLEANING,
    "standby": VacuumActivity.IDLE,
    "wall_clean": VacuumActivity.CLEANING,
    "wall_follow": VacuumActivity.CLEANING,
    "zone_clean": VacuumActivity.CLEANING,
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
                    TuyaVacuumEntity(
                        device,
                        manager,
                        charge_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.SWITCH_CHARGE, prefer_function=True
                        ),
                        fan_speed_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, DPCode.SUCTION, prefer_function=True
                        ),
                        locate_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.SEEK, prefer_function=True
                        ),
                        mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, DPCode.MODE, prefer_function=True
                        ),
                        pause_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.PAUSE
                        ),
                        status_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, DPCode.STATUS
                        ),
                        switch_wrapper=DPCodeBooleanWrapper.find_dpcode(
                            device, DPCode.POWER_GO, prefer_function=True
                        ),
                    )
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
        *,
        charge_wrapper: DPCodeBooleanWrapper | None,
        fan_speed_wrapper: DPCodeEnumWrapper | None,
        locate_wrapper: DPCodeBooleanWrapper | None,
        mode_wrapper: DPCodeEnumWrapper | None,
        pause_wrapper: DPCodeBooleanWrapper | None,
        status_wrapper: DPCodeEnumWrapper | None,
        switch_wrapper: DPCodeBooleanWrapper | None,
    ) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)
        self._charge_wrapper = charge_wrapper
        self._fan_speed_wrapper = fan_speed_wrapper
        self._locate_wrapper = locate_wrapper
        self._mode_wrapper = mode_wrapper
        self._pause_wrapper = pause_wrapper
        self._status_wrapper = status_wrapper
        self._switch_wrapper = switch_wrapper

        self._attr_fan_speed_list = []
        self._attr_supported_features = VacuumEntityFeature.SEND_COMMAND
        if status_wrapper or pause_wrapper:
            self._attr_supported_features |= VacuumEntityFeature.STATE
        if pause_wrapper:
            self._attr_supported_features |= VacuumEntityFeature.PAUSE

        if charge_wrapper or (
            mode_wrapper and TUYA_MODE_RETURN_HOME in mode_wrapper.options
        ):
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME

        if locate_wrapper:
            self._attr_supported_features |= VacuumEntityFeature.LOCATE

        if switch_wrapper:
            self._attr_supported_features |= (
                VacuumEntityFeature.STOP | VacuumEntityFeature.START
            )

        if fan_speed_wrapper:
            self._attr_fan_speed_list = fan_speed_wrapper.options
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._read_wrapper(self._fan_speed_wrapper)

    @property
    def activity(self) -> VacuumActivity | None:
        """Return Tuya vacuum device state."""
        if (status := self._read_wrapper(self._status_wrapper)) is not None:
            return TUYA_STATUS_TO_HA.get(status)

        if self._read_wrapper(self._pause_wrapper):
            return VacuumActivity.PAUSED
        return None

    async def async_start(self, **kwargs: Any) -> None:
        """Start the device."""
        await self._async_send_wrapper_updates(self._switch_wrapper, True)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        await self._async_send_wrapper_updates(self._switch_wrapper, False)

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        await self.async_stop(**kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        if self._charge_wrapper:
            await self._async_send_wrapper_updates(self._charge_wrapper, True)
        else:
            await self._async_send_wrapper_updates(
                self._mode_wrapper, TUYA_MODE_RETURN_HOME
            )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        await self._async_send_wrapper_updates(self._locate_wrapper, True)

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
