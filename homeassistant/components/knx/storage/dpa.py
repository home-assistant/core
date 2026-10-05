"""KNX Information Model semantics constants.

Datapoint application (DPA) identifiers grouped by their functional block (FB)
as defined by the KNX Information Model (KIM) and parsed from ETS project
semantics by xknxproject.
https://buildwithknxiot.knx.org/public-projects/knx-iot-docs/kim/functionalblock-overview/

Annotating a `GASelector` of an entity store schema with these makes the
entity suggestion provider assign matching project group addresses to that key.
No validation is done against them.
"""

from enum import StrEnum


class FB417(StrEnum):
    """FB 417 Light Switching Actuator Basic."""

    INFO_ON_OFF = "417.51"
    SWITCH_ON_OFF = "417.52"


class FB418(StrEnum):
    """FB 418 Light Dimming Actuator Basic."""

    INFO_ON_OFF = "418.51"
    ACTUAL_DIMMING_VALUE = "418.52"
    SWITCH_ON_OFF = "418.62"
    ABS_SETVALUE_CONTROL = "418.70"


class FB422(StrEnum):
    """FB 422 Colour Actuator xyY."""

    INFO_ON_OFF = "422.51"
    ACTUAL_DIMMING_VALUE = "422.52"
    CURRENT_COLOUR_XYY = "422.56"
    SWITCH_ON_OFF = "422.62"
    ABS_SETVALUE_CONTROL = "422.70"
    COLOUR_SET_XYY = "422.76"


class FB423(StrEnum):
    """FB 423 Colour Actuator RGB(W)."""

    COMBINED_SWITCH_ON_OFF = "423.51"
    COLOUR_SET_RGB = "423.52"
    COLOUR_SET_RGBW = "423.54"
    SWITCH_ON_OFF_RED = "423.56"
    ABS_SETVALUE_CONTROL_RED = "423.58"
    SWITCH_ON_OFF_GREEN = "423.59"
    ABS_SETVALUE_CONTROL_GREEN = "423.61"
    SWITCH_ON_OFF_BLUE = "423.62"
    ABS_SETVALUE_CONTROL_BLUE = "423.64"
    SWITCH_ON_OFF_WHITE = "423.65"
    ABS_SETVALUE_CONTROL_WHITE = "423.67"
    COMBINED_INFO_ON_OFF = "423.80"
    CURRENT_COLOUR_RGB = "423.81"
    CURRENT_COLOUR_RGBW = "423.82"
    ACTUAL_DIMMING_VALUE_RED = "423.83"
    ACTUAL_DIMMING_VALUE_GREEN = "423.84"
    ACTUAL_DIMMING_VALUE_BLUE = "423.85"
    ACTUAL_DIMMING_VALUE_WHITE = "423.86"


class FB427(StrEnum):
    """FB 427 Colour Temperature Actuator."""

    INFO_ON_OFF = "427.51"
    ACTUAL_DIMMING_VALUE = "427.52"
    SWITCH_ON_OFF = "427.62"
    ABS_SETVALUE_CONTROL = "427.70"
    CURRENT_COLOUR_TEMPERATURE = "427.75"
    ABS_COLOUR_TEMPERATURE_CONTROL = "427.81"


class FB800(StrEnum):
    """FB 800 Sunblind Actuator Basic."""

    CURRENT_ABS_POS_SLATS_PERCENT = "800.56"
    DEDICATED_STOP = "800.70"
    SET_ABS_POS_BLINDS_PERCENT = "800.71"
    SET_ABS_POS_SLATS_PERCENT = "800.72"
    MOVE_UP_DOWN = "800.81"
    STOP_STEP_UP_DOWN = "800.82"
    CURRENT_ABS_POS_BLINDS_PERCENT = "800.85"
