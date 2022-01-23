"""How bemfa represents HA entities."""

from typing import Any, Final

from homeassistant.components.binary_sensor import DOMAIN as BINAEY_SENSOR_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STOP,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_TEMPERATURE,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)

from .const import (
    MSG_OFF,
    MSG_ON,
    TOPIC_SUFFIX_CLIMATE,
    TOPIC_SUFFIX_COVER,
    TOPIC_SUFFIX_FAN,
    TOPIC_SUFFIX_LIGHT,
    TOPIC_SUFFIX_SENSOR,
    TOPIC_SUFFIX_SWITCH,
)

SUFFIX: Final = "suffix"
FILTER: Final = "filter"
GENERATE: Final = "generate"
RESOLVE: Final = "resolve"

SUPPORTED_HVAC_MODES = [
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
]

ENTITIES_CONFIG: Any = {
    SENSOR_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_SENSOR,
        FILTER: lambda attributes: ATTR_DEVICE_CLASS in attributes
        and attributes[ATTR_DEVICE_CLASS]
        in [
            DEVICE_CLASS_TEMPERATURE,
            DEVICE_CLASS_HUMIDITY,
            DEVICE_CLASS_ILLUMINANCE,
            DEVICE_CLASS_PM25,
        ],
        GENERATE: [
            lambda state, attributes: "",  # placeholder
            lambda state, attributes: state
            if attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TEMPERATURE
            else "",
            lambda state, attributes: state
            if attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_HUMIDITY
            else "",
            lambda state, attributes: "",
            lambda state, attributes: state
            if attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ILLUMINANCE
            else "",
            lambda state, attributes: state
            if attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_PM25
            else "",
        ],
    },
    BINAEY_SENSOR_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_SENSOR,
        GENERATE: [
            lambda state, attributes: "",  # placeholder
            lambda state, attributes: "",
            lambda state, attributes: "",
            lambda state, attributes: MSG_ON if state == STATE_ON else MSG_OFF,
        ],
    },
    SWITCH_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_SWITCH,
        GENERATE: [lambda state, attributes: MSG_ON if state == STATE_ON else MSG_OFF],
        RESOLVE: [
            (
                # split bemfa msg by "#", then take a sub list
                0,  # from this index
                1,  # to this index
                lambda msg, attributes: (  # and pass to this fun as param "msg"
                    SERVICE_TURN_ON if msg[0] == MSG_ON else SERVICE_TURN_OFF,
                    None,
                ),
            )
        ],
    },
    LIGHT_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_LIGHT,
        GENERATE: [
            lambda state, attributes: MSG_ON if state == STATE_ON else MSG_OFF,
            lambda state, attributes: round(attributes[ATTR_BRIGHTNESS] / 2.55)
            if ATTR_BRIGHTNESS in attributes
            else "",
        ],
        RESOLVE: [
            (
                0,
                2,
                lambda msg, attributes: (
                    SERVICE_TURN_ON if msg[0] == MSG_ON else SERVICE_TURN_OFF,
                    {ATTR_BRIGHTNESS_PCT: msg[1]} if len(msg) > 1 else None,
                ),
            )
        ],
    },
    COVER_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_COVER,
        GENERATE: [
            lambda state, attributes: MSG_OFF
            if ATTR_CURRENT_POSITION in attributes
            and attributes[ATTR_CURRENT_POSITION] == 0
            or ATTR_CURRENT_POSITION not in attributes
            and state == "closed"
            else MSG_ON,
            lambda state, attributes: attributes[ATTR_CURRENT_POSITION]
            if ATTR_CURRENT_POSITION in attributes
            else "",
        ],
        RESOLVE: [
            (
                0,
                2,
                lambda msg, attributes: (
                    SERVICE_SET_COVER_POSITION,
                    {ATTR_POSITION: msg[1]},
                )
                if len(msg) > 1
                else (
                    SERVICE_OPEN_COVER
                    if msg[0] == MSG_ON
                    else SERVICE_CLOSE_COVER
                    if msg[0] == MSG_OFF
                    else SERVICE_STOP_COVER,
                    None,
                ),
            )
        ],
    },
    FAN_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_FAN,
        GENERATE: [
            lambda state, attributes: MSG_ON if state == STATE_ON else MSG_OFF,
            lambda state, attributes: min(
                round(attributes[ATTR_PERCENTAGE] / attributes[ATTR_PERCENTAGE_STEP]), 4
            )
            if ATTR_PERCENTAGE in attributes and ATTR_PERCENTAGE_STEP in attributes
            else "",
            lambda state, attributes: 1
            if ATTR_OSCILLATING in attributes and attributes[ATTR_OSCILLATING]
            else 0
            if ATTR_OSCILLATING in attributes
            else "",
        ],
        RESOLVE: [
            (
                0,
                2,
                lambda msg, attributes: (
                    SERVICE_SET_PERCENTAGE,
                    {
                        ATTR_PERCENTAGE: min(
                            max(msg[1], 1) * attributes[ATTR_PERCENTAGE_STEP], 100
                        )
                    },
                )
                if len(msg) > 1 and ATTR_PERCENTAGE_STEP in attributes
                else (
                    SERVICE_TURN_ON if msg[0] == MSG_ON else SERVICE_TURN_OFF,
                    None,
                ),
            ),
            (
                2,
                3,
                lambda msg, attributes: (
                    SERVICE_OSCILLATE,
                    {ATTR_OSCILLATING: msg[0] == 1},
                ),
            ),
        ],
    },
    CLIMATE_DOMAIN: {
        SUFFIX: TOPIC_SUFFIX_CLIMATE,
        GENERATE: [
            lambda state, attributes: MSG_OFF if state == HVAC_MODE_OFF else MSG_ON,
            lambda state, attributes: SUPPORTED_HVAC_MODES.index(state) + 1
            if state in SUPPORTED_HVAC_MODES
            else "",
            lambda state, attributes: round(attributes[ATTR_TEMPERATURE])
            if ATTR_TEMPERATURE in attributes
            else "",
        ],
        RESOLVE: [
            (
                0,
                2,
                lambda msg, attributes: (
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_HVAC_MODE: SUPPORTED_HVAC_MODES[msg[1] - 1]},
                )
                if len(msg) > 1 and msg[1] >= 1 and msg[1] <= 5
                else (SERVICE_TURN_ON, None)
                if msg[0] == MSG_ON and len(msg) == 1
                else (SERVICE_TURN_OFF, None),
            ),
            (
                2,
                3,
                lambda msg, attributes: (
                    SERVICE_SET_TEMPERATURE,
                    {ATTR_TEMPERATURE: msg[0]},
                ),
            ),
        ],
    },
    VACUUM_DOMAIN: {  # fallback to switch
        SUFFIX: TOPIC_SUFFIX_SWITCH,
        GENERATE: [
            lambda state, attributes: MSG_ON
            if state in [STATE_ON, STATE_CLEANING]
            else MSG_OFF
        ],
        RESOLVE: [
            (
                0,
                1,
                lambda msg, attributes: (
                    SERVICE_START
                    if msg[0] == MSG_ON
                    and attributes[ATTR_SUPPORTED_FEATURES] & SUPPORT_START
                    else SERVICE_TURN_ON
                    if msg[0] == MSG_ON
                    else SERVICE_RETURN_TO_BASE
                    if msg[0] == MSG_OFF
                    and attributes[ATTR_SUPPORTED_FEATURES] & SUPPORT_RETURN_HOME
                    else SERVICE_STOP
                    if msg[0] == MSG_OFF
                    and attributes[ATTR_SUPPORTED_FEATURES] & SUPPORT_STOP
                    else SERVICE_TURN_OFF,
                    None,
                ),
            )
        ],
    },
}
