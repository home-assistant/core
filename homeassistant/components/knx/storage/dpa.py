"""KNX Information Model semantics constants.

Functional block (FB) and datapoint application (DPA) identifiers
as defined by the KNX Information Model (KIM) and parsed from
ETS project semantics by xknxproject.
https://buildwithknxiot.knx.org/public-projects/knx-iot-docs/kim/functionalblock-overview/

These are used to generate entity suggestions from project data in the
frontend - no validation is done against them.
"""

from typing import Final

from homeassistant.const import Platform

# FB 417 Light Switching Actuator Basic
DPA_417_INFO_ON_OFF: Final = "417.51"  # output
DPA_417_SWITCH_ON_OFF: Final = "417.52"  # input

# FB 418 Light Dimming Actuator Basic
DPA_418_INFO_ON_OFF: Final = "418.51"  # output
DPA_418_ACTUAL_DIMMING_VALUE: Final = "418.52"  # output
DPA_418_SWITCH_ON_OFF: Final = "418.62"  # input
DPA_418_ABS_SETVALUE_CONTROL: Final = "418.70"  # input

# FB 422 Colour Actuator xyY
DPA_422_INFO_ON_OFF: Final = "422.51"  # output
DPA_422_ACTUAL_DIMMING_VALUE: Final = "422.52"  # output
DPA_422_CURRENT_COLOUR_XYY: Final = "422.56"  # output
DPA_422_SWITCH_ON_OFF: Final = "422.62"  # input
DPA_422_ABS_SETVALUE_CONTROL: Final = "422.70"  # input
DPA_422_COLOUR_SET_XYY: Final = "422.76"  # input

# FB 423 Colour Actuator RGB(W)
DPA_423_COMBINED_SWITCH_ON_OFF: Final = "423.51"  # input
DPA_423_COLOUR_SET_RGB: Final = "423.52"  # input
DPA_423_COLOUR_SET_RGBW: Final = "423.54"  # input
DPA_423_SWITCH_ON_OFF_RED: Final = "423.56"  # input
DPA_423_ABS_SETVALUE_CONTROL_RED: Final = "423.58"  # input
DPA_423_SWITCH_ON_OFF_GREEN: Final = "423.59"  # input
DPA_423_ABS_SETVALUE_CONTROL_GREEN: Final = "423.61"  # input
DPA_423_SWITCH_ON_OFF_BLUE: Final = "423.62"  # input
DPA_423_ABS_SETVALUE_CONTROL_BLUE: Final = "423.64"  # input
DPA_423_SWITCH_ON_OFF_WHITE: Final = "423.65"  # input
DPA_423_ABS_SETVALUE_CONTROL_WHITE: Final = "423.67"  # input
DPA_423_COMBINED_INFO_ON_OFF: Final = "423.80"  # output
DPA_423_CURRENT_COLOUR_RGB: Final = "423.81"  # output
DPA_423_CURRENT_COLOUR_RGBW: Final = "423.82"  # output
DPA_423_ACTUAL_DIMMING_VALUE_RED: Final = "423.83"  # output
DPA_423_ACTUAL_DIMMING_VALUE_GREEN: Final = "423.84"  # output
DPA_423_ACTUAL_DIMMING_VALUE_BLUE: Final = "423.85"  # output
DPA_423_ACTUAL_DIMMING_VALUE_WHITE: Final = "423.86"  # output

# FB 427 Colour Temperature Actuator
DPA_427_INFO_ON_OFF: Final = "427.51"  # output
DPA_427_ACTUAL_DIMMING_VALUE: Final = "427.52"  # output
DPA_427_SWITCH_ON_OFF: Final = "427.62"  # input
DPA_427_ABS_SETVALUE_CONTROL: Final = "427.70"  # input
DPA_427_CURRENT_COLOUR_TEMPERATURE: Final = "427.75"  # output
DPA_427_ABS_COLOUR_TEMPERATURE_CONTROL: Final = "427.81"  # input

# FB 800 Sunblind Actuator Basic
DPA_800_CURRENT_ABS_POS_SLATS_PERCENT: Final = "800.56"  # output
DPA_800_DEDICATED_STOP: Final = "800.70"  # input
DPA_800_SET_ABS_POS_BLINDS_PERCENT: Final = "800.71"  # input
DPA_800_SET_ABS_POS_SLATS_PERCENT: Final = "800.72"  # input
DPA_800_MOVE_UP_DOWN: Final = "800.81"  # input
DPA_800_STOP_STEP_UP_DOWN: Final = "800.82"  # input
DPA_800_CURRENT_ABS_POS_BLINDS_PERCENT: Final = "800.85"  # output

# Maps functional block numbers to platforms suitable to represent them.
# The first platform in the list is used as default suggestion.
FUNCTIONAL_BLOCK_PLATFORMS: Final[dict[str, list[Platform]]] = {
    "417": [Platform.LIGHT, Platform.SWITCH],
    "418": [Platform.LIGHT],
    "422": [Platform.LIGHT],
    "423": [Platform.LIGHT],
    "427": [Platform.LIGHT],
    "800": [Platform.COVER],
}
