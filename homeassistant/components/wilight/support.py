"""Support for config validation using voluptuous and Translate Trigger."""

import calendar
import locale
import re
from typing import Any

import voluptuous as vol


def wilight_trigger(value: Any) -> str:
    """Check rules for WiLight Trigger."""
    err_desc = "Value is None"
    if value is not None:

        err_desc = "Expected a string"
        if isinstance(value, str):

            err_desc = "String should only contain 8 decimals character"
            regex = re.compile(r"^([0-9]{8})$")
            if regex.search(value):

                err_desc = "First 3 character should be less than 128"
                if int(value[0:3]) < 128:

                    err_desc = "Hour part should be less than 24"
                    if int(value[3:5]) < 24:

                        err_desc = "Minute part should be less than 60"
                        if int(value[5:7]) < 60:

                            err_desc = "Active part shoul be less than 2"
                            if int(value[7:8]) < 21:
                                return str(value)

    raise vol.Invalid(err_desc)


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
