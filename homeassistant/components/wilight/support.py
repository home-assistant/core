"""Support for config validation using voluptuous and Translate Trigger."""

import calendar
import locale
import re
from typing import Any

import voluptuous as vol


def wilight_trigger(value: Any) -> str:
    """Check rules for WiLight Trigger."""
    if value is None:
        raise vol.Invalid("Value is None")

    if not isinstance(value, str):
        raise vol.Invalid("Expected a string")

    regex = re.compile(r"^([0-9]{8})$")
    if not regex.search(value):
        raise vol.Invalid("String should only contain 8 decimals character")

    if int(value[0:3]) > 127:
        raise vol.Invalid("First 3 character should be less than 127")

    if int(value[3:5]) > 23:
        raise vol.Invalid("Hour part should be less than 24")

    if int(value[5:7]) > 59:
        raise vol.Invalid("Minute part should be less than 60")

    if int(value[7:8]) > 1:
        raise vol.Invalid("Active part shoul be less than 2")

    return str(value)


def wilight_to_hass_trigger(value):
    """Convert wilight trigger to hass description."""
    if value is None:
        return value

    # locale.setlocale(locale.LC_ALL, 'pt_BR')
    locale.setlocale(locale.LC_ALL, "")
    week_days = list(calendar.day_abbr)
    days = bin(int(value[0:3]))[2:].zfill(8)
    desc = ""
    if int(days[7:8]) == 1:
        desc = desc + week_days[6] + " "
    if int(days[6:7]) == 1:
        desc = desc + week_days[0] + " "
    if int(days[5:6]) == 1:
        desc = desc + week_days[1] + " "
    if int(days[4:5]) == 1:
        desc = desc + week_days[2] + " "
    if int(days[3:4]) == 1:
        desc = desc + week_days[3] + " "
    if int(days[2:3]) == 1:
        desc = desc + week_days[4] + " "
    if int(days[1:2]) == 1:
        desc = desc + week_days[5] + " "
    desc = desc + value[3:5] + ":" + value[5:7] + " "
    if int(value[7:8]) == 1:
        desc = desc + "On"
    else:
        desc = desc + "Off"

    return desc
