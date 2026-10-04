"""Electra Smart air conditioner device model (vendored from pyElectra).

See ``NOTICE.md`` in this package for provenance and the divergences from
upstream.
"""

import json
from typing import Any

from .const import Feature, OperationMode


class ElectraAirConditioner:
    """Model of an Electra smart air conditioner device."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize an air conditioner from a device record."""
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.regdate: str = data["regdate"]
        self.model = data["model"]
        self.mac: str = data["mac"]
        self.serial_number: str = data["sn"]
        self.manufactor: str = data["manufactor"]
        self.type: str = data["deviceTypeName"]
        self.status: str = data["status"]
        # deviceToken was historically sent by the Electra API for every unit,
        # but it can be omitted entirely for some devices, which crashed setup.
        # The token is not used anywhere downstream, so default it safely.
        self.token: str = data.get("deviceToken", "")
        self._time_delta: int = 0
        self.features: list[int] = []

        self.current_mode: str | None = None
        self.collected_measure: int | None = None
        self._oper_data: dict[str, str] = {}

    def is_disconnected(self, thresh_sec: int = 60) -> bool:
        """Return True if the last telemetry is older than the threshold."""
        return self._time_delta > thresh_sec

    def update_features(self) -> None:
        """Expose swing features advertised in the operation data."""
        if "VSWING" in self._oper_data:
            self.features.append(Feature.V_SWING)
        if "HSWING" in self._oper_data:
            self.features.append(Feature.H_SWING)

    def get_sensor_temperature(self) -> int | None:
        """Return the raw sensor temperature reading."""
        return self.collected_measure

    def get_mode(self) -> str:
        """Return the current AC mode."""
        return self._oper_data["AC_MODE"]

    def set_mode(self, mode: str) -> None:
        """Set the AC mode."""
        if mode in [
            OperationMode.MODE_AUTO,
            OperationMode.MODE_COOL,
            OperationMode.MODE_DRY,
            OperationMode.MODE_FAN,
            OperationMode.MODE_HEAT,
        ]:
            if mode != self._oper_data["AC_MODE"]:
                self._oper_data["AC_MODE"] = mode

    def set_horizontal_swing(self, enable: bool) -> None:
        """Enable or disable horizontal swing."""
        if "HSWING" in self._oper_data:
            self._oper_data["HSWING"] = OperationMode.ON if enable else OperationMode.OFF

    def set_vertical_swing(self, enable: bool) -> None:
        """Enable or disable vertical swing."""
        if "VSWING" in self._oper_data:
            self._oper_data["VSWING"] = OperationMode.ON if enable else OperationMode.OFF

    def is_vertical_swing(self) -> bool:
        """Return True if vertical swing is enabled."""
        if "VSWING" in self._oper_data:
            return self._oper_data["VSWING"] == OperationMode.ON
        return False

    def is_horizontal_swing(self) -> bool:
        """Return True if horizontal swing is enabled."""
        if "HSWING" in self._oper_data:
            return self._oper_data["HSWING"] == OperationMode.ON
        return False

    def is_on(self) -> bool:
        """Return True if the AC is turned on."""
        if "TURN_ON_OFF" in self._oper_data:
            return self._oper_data["TURN_ON_OFF"] == OperationMode.ON
        return self._oper_data["AC_MODE"] != OperationMode.STANDBY

    def turn_on(self) -> None:
        """Turn the AC on."""
        if not self.is_on() and "TURN_ON_OFF" in self._oper_data:
            self._oper_data["TURN_ON_OFF"] = OperationMode.ON

    def turn_off(self) -> None:
        """Turn the AC off."""
        if self.is_on():
            if "TURN_ON_OFF" in self._oper_data:
                self._oper_data["TURN_ON_OFF"] = OperationMode.OFF
            else:
                self._oper_data["AC_MODE"] = OperationMode.STANDBY

    def get_temperature(self) -> int:
        """Return the target temperature."""
        return int(self._oper_data["SPT"])

    def set_temperature(self, val: int) -> None:
        """Set the target temperature."""
        if self.get_temperature() != val:
            self._oper_data["SPT"] = str(val)

    def get_fan_speed(self) -> str:
        """Return the fan speed."""
        return self._oper_data["FANSPD"]

    def set_fan_speed(self, speed: str) -> None:
        """Set the fan speed."""
        if speed in [
            OperationMode.FAN_SPEED_AUTO,
            OperationMode.FAN_SPEED_HIGH,
            OperationMode.FAN_SPEED_MED,
            OperationMode.FAN_SPEED_LOW,
        ]:
            if speed != self._oper_data["FANSPD"]:
                self._oper_data["FANSPD"] = speed

    def set_turbo_mode(self, enable: bool) -> None:
        """Enable or disable turbo mode."""
        self._oper_data["TURBO"] = OperationMode.ON if enable else OperationMode.OFF

    def get_turbo_mode(self) -> bool:
        """Return True if turbo mode is enabled."""
        return self._oper_data["TURBO"] == OperationMode.ON

    def set_shabat_mode(self, enable: bool) -> None:
        """Enable or disable Shabat mode."""
        self._oper_data["SHABAT"] = OperationMode.ON if enable else OperationMode.OFF

    def get_shabat_mode(self) -> bool:
        """Return True if Shabat mode is enabled."""
        return self._oper_data["SHABAT"] == OperationMode.ON

    def update_operation_states(self, data: dict[str, Any]) -> None:
        """Apply the latest telemetry payload to the device."""
        self._oper_data = json.loads(data["commandJson"]["OPER"])["OPER"]
        self._time_delta = data["timeDelta"]
        measurments = json.loads(data["commandJson"]["DIAG_L2"])["DIAG_L2"]
        if "I_RAT" in measurments:
            self.collected_measure = int(measurments["I_RAT"])
        if "I_CALC_AT" in measurments:
            self.collected_measure = int(measurments["I_CALC_AT"])

        self.current_mode = measurments["O_ODU_MODE"]

    def get_operation_state(self) -> str:
        """Return the operation state payload to send to the API."""
        if "AC_STSRC" in self._oper_data:
            self._oper_data["AC_STSRC"] = "WI-FI"

        return json.dumps({"OPER": self._oper_data})
