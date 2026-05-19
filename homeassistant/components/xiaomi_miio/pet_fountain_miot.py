"""Local Xiaomi Pet Fountain implementation for xiaomi_miio."""

from __future__ import annotations

from datetime import time
import enum
from typing import Any

from miio.miot_device import DeviceStatus, MiotDevice

from .const import MODEL_PET_FOUNTAIN_70M2


class PetFountainStatus(enum.Enum):
    """The fountain operating status."""

    NoWater = "no_water"
    Watering = "watering"


class PetFountainMode(enum.Enum):
    """The fountain water mode."""

    Auto = "auto"
    Interval = "interval"
    Continuous = "continuous"


class ChargingState(enum.Enum):
    """The fountain charging state."""

    NotCharging = "not_charging"
    Charging = "charging"
    Charged = "charged"


def _seconds_to_time(value: int) -> time:
    value %= 24 * 60 * 60
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return time(hour=hours, minute=minutes, second=seconds)


def _time_to_seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


class XiaomiPetFountainStatus(DeviceStatus):
    """Container for status reports from Xiaomi Pet Fountain 2."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the status container."""
        self.data = data

    @property
    def is_on(self) -> bool:
        """Return true to keep option entities available."""
        return True

    @property
    def fault_code(self) -> int | None:
        """Return the raw fault code."""
        raw_fault = self.data.get("fault_code")
        if not isinstance(raw_fault, int):
            return None
        return raw_fault

    @property
    def has_fault(self) -> bool:
        """Return true when the device reports a fault."""
        code = self.fault_code
        return code is not None and code > 0

    @property
    def status(self) -> PetFountainStatus | None:
        """Return the fountain operating status."""
        raw_status = self.data.get("status")
        if not isinstance(raw_status, int):
            return None
        return {
            1: PetFountainStatus.NoWater,
            2: PetFountainStatus.Watering,
        }.get(raw_status)

    @property
    def mode(self) -> PetFountainMode | None:
        """Return the configured water mode."""
        raw_mode = self.data.get("mode")
        if not isinstance(raw_mode, int):
            return None
        return {
            0: PetFountainMode.Auto,
            1: PetFountainMode.Interval,
            2: PetFountainMode.Continuous,
        }.get(raw_mode)

    @property
    def water_interval(self) -> int | None:
        """Return the configured water interval in minutes."""
        return self.data.get("water_interval")

    @property
    def water_shortage(self) -> bool | None:
        """Return true when the fountain is low on water."""
        return self.data.get("water_shortage")

    @property
    def filter_life_remaining(self) -> int | None:
        """Return the remaining filter life in percent."""
        return self.data.get("filter_life_remaining")

    @property
    def filter_left_time(self) -> float | None:
        """Return the remaining filter time in days."""
        if (value := self.data.get("filter_left_time")) is None:
            return None
        return round(value / 24, 2)

    @property
    def child_lock(self) -> bool | None:
        """Return true when physical controls are locked."""
        return self.data.get("child_lock")

    @property
    def battery(self) -> int | None:
        """Return battery level percentage."""
        return self.data.get("battery")

    @property
    def charging_state(self) -> ChargingState | None:
        """Return the charging state."""
        raw_state = self.data.get("charging_state")
        if not isinstance(raw_state, int):
            return None
        return {
            0: ChargingState.NotCharging,
            1: ChargingState.Charging,
            2: ChargingState.Charged,
        }.get(raw_state)

    @property
    def do_not_disturb(self) -> bool | None:
        """Return true when do not disturb is enabled."""
        return self.data.get("do_not_disturb")

    @property
    def low_battery(self) -> bool | None:
        """Return true when the device reports low battery."""
        return self.data.get("low_battery")

    @property
    def usb_power(self) -> bool | None:
        """Return true when USB power is connected."""
        return self.data.get("usb_power")

    @property
    def dnd_start(self) -> time | None:
        """Return the DnD start time."""
        if (value := self.data.get("dnd_start")) is None:
            return None
        return _seconds_to_time(value)

    @property
    def dnd_end(self) -> time | None:
        """Return the DnD end time."""
        if (value := self.data.get("dnd_end")) is None:
            return None
        return _seconds_to_time(value)

    @property
    def pump_blocked(self) -> bool | None:
        """Return true when the pump is blocked."""
        return self.data.get("pump_blocked")


class XiaomiPetFountain(MiotDevice):
    """Main class representing Xiaomi Pet Fountain 2."""

    _mappings = {
        MODEL_PET_FOUNTAIN_70M2: {
            "fault_code": {"siid": 2, "piid": 1},
            "status": {"siid": 2, "piid": 3},
            "mode": {"siid": 2, "piid": 4},
            "water_shortage": {"siid": 2, "piid": 10},
            "water_interval": {"siid": 2, "piid": 11},
            "filter_life_remaining": {"siid": 3, "piid": 1},
            "filter_left_time": {"siid": 3, "piid": 2},
            "reset_filter_life": {"siid": 3, "aiid": 1},
            "child_lock": {"siid": 4, "piid": 1},
            "battery": {"siid": 5, "piid": 1},
            "charging_state": {"siid": 5, "piid": 2},
            "do_not_disturb": {"siid": 6, "piid": 1},
            "low_battery": {"siid": 9, "piid": 5},
            "usb_power": {"siid": 9, "piid": 6},
            "dnd_start": {"siid": 9, "piid": 10},
            "dnd_end": {"siid": 9, "piid": 11},
            "pump_blocked": {"siid": 9, "piid": 12},
        }
    }

    def status(self) -> XiaomiPetFountainStatus:
        """Retrieve properties."""
        data = {
            prop["did"]: prop["value"] if prop["code"] == 0 else None
            for prop in self.get_properties_for_mapping()
        }
        return XiaomiPetFountainStatus(data)

    def set_mode(self, mode: PetFountainMode) -> list[dict[str, Any]]:
        """Set the water dispensing mode."""
        raw_mode = {
            PetFountainMode.Auto: 0,
            PetFountainMode.Interval: 1,
            PetFountainMode.Continuous: 2,
        }[mode]
        return self.set_property("mode", raw_mode)

    def set_water_interval(self, minutes: int) -> list[dict[str, Any]]:
        """Set the interval mode water interval in minutes."""
        return self.set_property("water_interval", minutes)

    def set_child_lock(self, enabled: bool) -> list[dict[str, Any]]:
        """Set the child lock."""
        return self.set_property("child_lock", enabled)

    def set_do_not_disturb(self, enabled: bool) -> list[dict[str, Any]]:
        """Set do not disturb mode."""
        return self.set_property("do_not_disturb", enabled)

    def reset_filter_life(self) -> dict[str, Any]:
        """Reset filter life."""
        action = self._get_mapping()["reset_filter_life"]
        return self.call_action_by(action["siid"], action["aiid"])

    def set_dnd_start(self, value: time) -> list[dict[str, Any]]:
        """Set the DnD start time."""
        return self.set_property("dnd_start", _time_to_seconds(value))

    def set_dnd_end(self, value: time) -> list[dict[str, Any]]:
        """Set the DnD end time."""
        return self.set_property("dnd_end", _time_to_seconds(value))
