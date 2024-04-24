"""Support for config validation using voluptuous and Translate Trigger."""

from __future__ import annotations

import calendar
import locale
import re
from typing import Any

import voluptuous as vol


def wilight_trigger(value: Any) -> str | None:
    """Check rules for WiLight Trigger."""
    step = 1
    err_desc = "Value is None"
    result_128 = False
    result_24 = False
    result_60 = False
    result_2 = False

    if value is not None:
        step = 2
        err_desc = "Expected a string"

    if (step == 2) & isinstance(value, str):
        step = 3
        err_desc = "String should only contain 8 decimals character"
        if re.search(r"^([0-9]{8})$", value) is not None:
            step = 4
            err_desc = "First 3 character should be less than 128"
            result_128 = int(value[0:3]) < 128
            result_24 = int(value[3:5]) < 24
            result_60 = int(value[5:7]) < 60
            result_2 = int(value[7:8]) < 2

    if (step == 4) & result_128:
        step = 5
        err_desc = "Hour part should be less than 24"

    if (step == 5) & result_24:
        step = 6
        err_desc = "Minute part should be less than 60"

    if (step == 6) & result_60:
        step = 7
        err_desc = "Active part should be less than 2"

    if (step == 7) & result_2:
        return value

    raise vol.Invalid(err_desc)


def wilight_to_hass_trigger(value: str | None) -> str | None:
    """Convert wilight trigger to hass description.

    Ex: "12719001" -> "sun mon tue wed thu fri sat 19:00 On"
        "00000000" -> "00:00 Off"
    """
    if value is None:
        return value

    locale.setlocale(locale.LC_ALL, "")
    week_days = list(calendar.day_abbr)
    days = bin(int(value[0:3]))[2:].zfill(8)
    desc = ""
    if int(days[7:8]) == 1:
        desc += f"{week_days[6]} "
    if int(days[6:7]) == 1:
        desc += f"{week_days[0]} "
    if int(days[5:6]) == 1:
        desc += f"{week_days[1]} "
    if int(days[4:5]) == 1:
        desc += f"{week_days[2]} "
    if int(days[3:4]) == 1:
        desc += f"{week_days[3]} "
    if int(days[2:3]) == 1:
        desc += f"{week_days[4]} "
    if int(days[1:2]) == 1:
        desc += f"{week_days[5]} "
    desc += f"{value[3:5]}:{value[5:7]} "
    if int(value[7:8]) == 1:
        desc += "On"
    else:
        desc += "Off"

    return desc
