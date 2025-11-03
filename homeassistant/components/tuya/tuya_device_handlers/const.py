"""Constants for Tuya device handlers."""

from __future__ import annotations

from enum import StrEnum


class TuyaDPCode(StrEnum):
    """Tuya data-point codes."""

    CHILD_LOCK = "child_lock"
    CONTROL = "control"
    CONTROL_BACK_MODE = "control_back_mode"
    PERCENT_CONTROL = "percent_control"
    TEMP_SET = "temp_set"
    TIME_TOTAL = "time_total"
    UPPER_TEMP = "upper_temp"


class TuyaDeviceCategory(StrEnum):
    """Tuya device categories."""

    CL = "cl"
    """Curtain

    https://developer.tuya.com/en/docs/iot/categorycl?id=Kaiuz1hnpo7df
    """
    WK = "wk"
    """Thermostat

    https://developer.tuya.com/en/docs/iot/f?id=K9gf45ld5l0t9
    """
