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
from .const import TUYA_DISCOVERY_NEW, DPCode, DPType
from .entity import EnumTypeData, IntegerTypeData, TuyaEntity

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
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya vacuum."""
        entities: list[TuyaVacuumEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if device.category == "sd":
                entities.append(TuyaVacuumEntity(device, hass_data.manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaVacuumEntity(TuyaEntity, StateVacuumEntity):
    """Tuya Vacuum Device."""

    _fan_speed: EnumTypeData | None = None
    _battery_level: IntegerTypeData | None = None
    _attr_name = None

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Init Tuya vacuum."""
        super().__init__(device, device_manager)

        self._attr_fan_speed_list = []

        self._attr_supported_features = (
            VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.STATE
        )
        if self.find_dpcode(DPCode.PAUSE, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.PAUSE

        self._return_home_use_switch_charge = False
        if self.find_dpcode(DPCode.SWITCH_CHARGE, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME
            self._return_home_use_switch_charge = True
        elif (
            (
                enum_type := self.find_dpcode(
                    DPCode.MODE, dptype=DPType.ENUM, prefer_function=True
                )
            )
            and TUYA_MODE_RETURN_HOME in enum_type.range
        ):
            self._attr_supported_features |= VacuumEntityFeature.RETURN_HOME

        if self.find_dpcode(DPCode.SEEK, prefer_function=True):
            self._attr_supported_features |= VacuumEntityFeature.LOCATE

        if self.find_dpcode(DPCode.POWER_GO, prefer_function=True):
            self._attr_supported_features |= (
                VacuumEntityFeature.STOP | VacuumEntityFeature.START
            )

        if enum_type := self.find_dpcode(
            DPCode.SUCTION, dptype=DPType.ENUM, prefer_function=True
        ):
            self._fan_speed = enum_type
            self._attr_fan_speed_list = enum_type.range
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED

        if int_type := self.find_dpcode(DPCode.ELECTRICITY_LEFT, dptype=DPType.INTEGER):
            self._attr_supported_features |= VacuumEntityFeature.BATTERY
            self._battery_level = int_type

    @property
    def battery_level(self) -> int | None:
        """Return Tuya device state."""
        if self._battery_level is None or not (
            status := self.device.status.get(DPCode.ELECTRICITY_LEFT)
        ):
            return None
        return round(self._battery_level.scale_value(status))

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.status.get(DPCode.SUCTION)

    @property
    def activity(self) -> VacuumActivity | None:
        """Return Tuya vacuum device state."""
        if self.device.status.get(DPCode.PAUSE) and not (
            self.device.status.get(DPCode.STATUS)
        ):
            return VacuumActivity.PAUSED
        if not (status := self.device.status.get(DPCode.STATUS)):
            return None
        return TUYA_STATUS_TO_HA.get(status)

    def start(self, **kwargs: Any) -> None:
        """Start the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": True}])

    def stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def pause(self, **kwargs: Any) -> None:
        """Pause the device."""
        self._send_command([{"code": DPCode.POWER_GO, "value": False}])

    def return_to_base(self, **kwargs: Any) -> None:
        """Return device to dock."""
        if self._return_home_use_switch_charge:
            self._send_command([
                {"code": DPCode.SWITCH_CHARGE, "value": True}
            ])
        else:
            self._send_command([
                {"code": DPCode.MODE, "value": TUYA_MODE_RETURN_HOME}
            ])

    def locate(self, **kwargs: Any) -> None:
        """Locate the device."""
        self._send_command([{"code": DPCode.SEEK, "value": True}])

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._send_command([{"code": DPCode.SUCTION, "value": fan_speed}])

    def send_command(
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
        self._send_command([{"code": command, "value": params[0]}])
