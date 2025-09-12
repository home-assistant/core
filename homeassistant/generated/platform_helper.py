"""Automatically generated file.

To update, run python3 -m script.hassfest
"""

from enum import StrEnum


class HelperPlatform(StrEnum):
    """Available helper platforms."""

    COUNTER = "counter"
    DERIVATIVE = "derivative"
    FILTER = "filter"
    GENERIC_HYGROSTAT = "generic_hygrostat"
    GENERIC_THERMOSTAT = "generic_thermostat"
    GROUP = "group"
    HISTORY_STATS = "history_stats"
    INPUT_BOOLEAN = "input_boolean"
    INPUT_BUTTON = "input_button"
    INPUT_DATETIME = "input_datetime"
    INPUT_NUMBER = "input_number"
    INPUT_SELECT = "input_select"
    INPUT_TEXT = "input_text"
    INTEGRATION = "integration"
    MANUAL = "manual"
    MIN_MAX = "min_max"
    MOLD_INDICATOR = "mold_indicator"
    RANDOM = "random"
    SCHEDULE = "schedule"
    STATISTICS = "statistics"
    SWITCH_AS_X = "switch_as_x"
    TEMPLATE = "template"
    THRESHOLD = "threshold"
    TIMER = "timer"
    TOD = "tod"
    TREND = "trend"
    UTILITY_METER = "utility_meter"
