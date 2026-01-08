"""Support for Tuya Vacuums."""

from __future__ import annotations

from typing import Any, Self

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
from .models import DeviceWrapper, DPCodeBooleanWrapper, DPCodeEnumWrapper


class _VacuumActivityWrapper(DeviceWrapper):
    """Wrapper for the state of a device."""

    _TUYA_STATUS_TO_HA = {
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

    def __init__(
        self,
        pause_wrapper: DPCodeBooleanWrapper | None = None,
        status_wrapper: DPCodeEnumWrapper | None = None,
    ) -> None:
        """Init _VacuumActivityWrapper."""
        self._pause_wrapper = pause_wrapper
        self._status_wrapper = status_wrapper

    @classmethod
    def find_dpcode(cls, device: CustomerDevice) -> Self | None:
        """Find and return a _VacuumActivityWrapper for the given DP codes."""
        pause_wrapper = DPCodeBooleanWrapper.find_dpcode(device, DPCode.PAUSE)
        status_wrapper = DPCodeEnumWrapper.find_dpcode(device, DPCode.STATUS)
        if pause_wrapper or status_wrapper:
            return cls(pause_wrapper=pause_wrapper, status_wrapper=status_wrapper)
        return None

    def read_device_status(self, device: CustomerDevice) -> VacuumActivity | None:
        """Read the device status."""
        if (
            self._status_wrapper
            and (status := self._status_wrapper.read_device_status(device)) is not None
        ):
            return self._TUYA_STATUS_TO_HA.get(status)

        if self._pause_wrapper and self._pause_wrapper.read_device_status(device):
            return VacuumActivity.PAUSED
        return None


class _VacuumActionWrapper(DeviceWrapper):
    """Wrapper for sending actions to a vacuum."""

    _TUYA_MODE_RETURN_HOME = "chargego"

    def __init__(
        self,
        charge_wrapper: DPCodeBooleanWrapper | None,
        locate_wrapper: DPCodeBooleanWrapper | None,
        pause_wrapper: DPCodeBooleanWrapper | None,
        mode_wrapper: DPCodeEnumWrapper | None,
        switch_wrapper: DPCodeBooleanWrapper | None,
    ) -> None:
        """Init _VacuumActionWrapper."""
        self._charge_wrapper = charge_wrapper
        self._locate_wrapper = locate_wrapper
        self._mode_wrapper = mode_wrapper
        self._switch_wrapper = switch_wrapper

        self.options = []
        if charge_wrapper or (
            mode_wrapper and self._TUYA_MODE_RETURN_HOME in mode_wrapper.options
        ):
            self.options.append("return_to_base")
        if locate_wrapper:
            self.options.append("locate")
        if pause_wrapper:
            self.options.append("pause")
        if switch_wrapper:
            self.options.append("start")
            self.options.append("stop")

    @classmethod
    def find_dpcode(cls, device: CustomerDevice) -> Self:
        """Find and return a _VacuumActionWrapper for the given DP codes."""
        return cls(
            charge_wrapper=DPCodeBooleanWrapper.find_dpcode(
                device, DPCode.SWITCH_CHARGE, prefer_function=True
            ),
            locate_wrapper=DPCodeBooleanWrapper.find_dpcode(
                device, DPCode.SEEK, prefer_function=True
            ),
            mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                device, DPCode.MODE, prefer_function=True
            ),
            pause_wrapper=DPCodeBooleanWrapper.find_dpcode(device, DPCode.PAUSE),
            switch_wrapper=DPCodeBooleanWrapper.find_dpcode(
                device, DPCode.POWER_GO, prefer_function=True
            ),
        )

    def get_update_commands(
        self, device: CustomerDevice, value: Any
    ) -> list[dict[str, Any]]:
        """Get the commands for the action wrapper."""
        if value == "locate" and self._locate_wrapper:
            return self._locate_wrapper.get_update_commands(device, True)
        if value == "pause" and self._switch_wrapper:
            return self._switch_wrapper.get_update_commands(device, False)
        if value == "return_to_base":
            if self._charge_wrapper:
                return self._charge_wrapper.get_update_commands(device, True)
            if self._mode_wrapper:
                return self._mode_wrapper.get_update_commands(
                    device, self._TUYA_MODE_RETURN_HOME
                )
        if value == "start" and self._switch_wrapper:
            return self._switch_wrapper.get_update_commands(device, True)
        if value == "stop" and self._switch_wrapper:
            return self._switch_wrapper.get_update_commands(device, False)
        return []


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
                        action_wrapper=_VacuumActionWrapper.find_dpcode(device),
                        activity_wrapper=_VacuumActivityWrapper.find_dpcode(device),
                        fan_speed_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, DPCode.SUCTION, prefer_function=True
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
        action_wrapper: DeviceWrapper[str] | None,
        activity_wrapper: DeviceWrapper[VacuumActivity] | None,
        fan_speed_wrapper: DeviceWrapper[str] | None,
    ) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)
        self._action_wrapper = action_wrapper
        self._activity_wrapper = activity_wrapper
        self._fan_speed_wrapper = fan_speed_wrapper

        self._attr_fan_speed_list = []
        self._attr_supported_features = VacuumEntityFeature.SEND_COMMAND

        if action_wrapper:
            if "pause" in action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.PAUSE
            if "return_to_base" in action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME
            if "locate" in action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.LOCATE
            if "start" in action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.START
            if "stop" in action_wrapper.options:
                self._attr_supported_features |= VacuumEntityFeature.STOP

        if activity_wrapper:
            self._attr_supported_features |= VacuumEntityFeature.STATE

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
        return self._read_wrapper(self._activity_wrapper)

    async def async_start(self, **kwargs: Any) -> None:
        """Start the device."""
        await self._async_send_wrapper_updates(self._action_wrapper, "start")

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        await self._async_send_wrapper_updates(self._action_wrapper, "stop")

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        await self._async_send_wrapper_updates(self._action_wrapper, "pause")

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        await self._async_send_wrapper_updates(self._action_wrapper, "return_to_base")

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        await self._async_send_wrapper_updates(self._action_wrapper, "locate")

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
