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


def functional_block(dpa: str) -> str:
    """Return the functional block number of a DPA identifier - "417" of "417.52"."""
    return dpa.partition(".")[0]


class FB180(StrEnum):
    """FB 180 DHW Temperature Sensor."""

    TEMP_DHW = "180.51"


class FB187(StrEnum):
    """FB 187 Collector Temperature Sensor."""

    TEMP_COLLECTOR = "187.51"


class FB320(StrEnum):
    """FB 320 Outside Temperature Sensor."""

    TEMP_OUTSIDE = "320.51"


class FB321(StrEnum):
    """FB 321 Room Temperature Sensor."""

    TEMP_ROOM = "321.51"


class FB322(StrEnum):
    """FB 322 Supply Air Temperature Sensor."""

    TEMP_SUPPLY_AIR = "322.51"


class FB323(StrEnum):
    """FB 323 Return Air Temperature Sensor."""

    TEMP_RETURN_AIR = "323.51"


class FB324(StrEnum):
    """FB 324 Flow Water Temperature Sensor."""

    TEMP_FLOW_WATER = "324.51"


class FB325(StrEnum):
    """FB 325 Return Water Temperature Sensor."""

    TEMP_RETURN_WATER = "325.51"


class FB326(StrEnum):
    """FB 326 Condenser Flow Water Temperature Sensor."""

    TEMP_FLOW_WATER_COND = "326.51"


class FB327(StrEnum):
    """FB 327 Condenser Return Water Temperature Sensor."""

    TEMP_RETURN_WATER_COND = "327.51"


class FB328(StrEnum):
    """FB 328 Discharge Temperature Sensor."""

    TEMP_DISCHARGE_AIR = "328.51"


class FB329(StrEnum):
    """FB 329 Floor Temperature Sensor."""

    TEMP_FLOOR = "329.51"


class FB330(StrEnum):
    """FB 330 Outside AQ Sensor."""

    AQ_OUTSIDE = "330.51"


class FB331(StrEnum):
    """FB 331 Room AQ Sensor."""

    AQ_ROOM = "331.51"


class FB332(StrEnum):
    """FB 332 Supply AQ Sensor."""

    AQ_SUPPLY_AIR = "332.51"


class FB333(StrEnum):
    """FB 333 Return AQ Sensor."""

    AQ_RETURN_AIR = "333.51"


class FB336(StrEnum):
    """FB 336 Outside Relative Humidity Sensor."""

    HUM_REL_OUTSIDE = "336.51"


class FB337(StrEnum):
    """FB 337 Room Relative Humidity Sensor."""

    HUM_REL_ROOM = "337.51"


class FB338(StrEnum):
    """FB 338 Supply Air Relative Humidity Sensor."""

    HUM_REL_SUPPLY_AIR = "338.51"


class FB339(StrEnum):
    """FB 339 Return Air Relative Humidity Sensor."""

    HUM_REL_RETURN_AIR = "339.51"


class FB348(StrEnum):
    """FB 348 Sun Intensity Sensor."""

    SUN_INTENSITY = "348.51"


class FB409(StrEnum):
    """FB 409 Indoor Brightness Sensor."""

    ROOM_ILLUMINATION = "409.51"


class FB410(StrEnum):
    """FB 410 Indoor Luminance Sensor."""

    INDOOR_LUMINANCE = "410.51"


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


class FB1013(StrEnum):
    """FB 1013 Atmospheric Pressure Sensor."""

    ATMOSPHERIC_PRESSURE_ABS = "1013.51"


class FB1015(StrEnum):
    """FB 1015 General Purpose Analog Input."""

    ANALOG_INPUT_VALUE = "1015.51"


class FB1016(StrEnum):
    """FB 1016 General Purpose Temperature Sensor."""

    TEMP_VALUE = "1016.51"


class FB1019(StrEnum):
    """FB 1019 General Purpose Analog Output."""

    ANALOG_OUT_SETP = "1019.51"
    STATUS_ANALOG_OUTPUT = "1019.52"
