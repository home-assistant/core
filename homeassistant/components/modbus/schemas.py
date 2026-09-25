"""Probatio schemas for the Modbus integration."""

import probatio

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COUNT,
    CONF_COVERS,
    CONF_DELAY,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_LIGHTS,
    CONF_METHOD,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_SWITCHES,
    CONF_TEMPERATURE_UNIT,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolSchemaType

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_X_COILS,
    CALL_TYPE_X_REGISTER_HOLDINGS,
    CONF_BAUDRATE,
    CONF_BRIGHTNESS_REGISTER,
    CONF_BYTESIZE,
    CONF_CLIMATES,
    CONF_COLOR_TEMP_REGISTER,
    CONF_CURRENT_TEMP_OFFSET,
    CONF_CURRENT_TEMP_SCALE,
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_FAN_MODE_AUTO,
    CONF_FAN_MODE_DIFFUSE,
    CONF_FAN_MODE_FOCUS,
    CONF_FAN_MODE_HIGH,
    CONF_FAN_MODE_LOW,
    CONF_FAN_MODE_MEDIUM,
    CONF_FAN_MODE_MIDDLE,
    CONF_FAN_MODE_OFF,
    CONF_FAN_MODE_ON,
    CONF_FAN_MODE_REGISTER,
    CONF_FAN_MODE_TOP,
    CONF_FAN_MODE_VALUES,
    CONF_FANS,
    CONF_HVAC_ACTION_COOLING,
    CONF_HVAC_ACTION_DEFROSTING,
    CONF_HVAC_ACTION_DRYING,
    CONF_HVAC_ACTION_FAN,
    CONF_HVAC_ACTION_HEATING,
    CONF_HVAC_ACTION_IDLE,
    CONF_HVAC_ACTION_OFF,
    CONF_HVAC_ACTION_PREHEATING,
    CONF_HVAC_ACTION_REGISTER,
    CONF_HVAC_ACTION_VALUES,
    CONF_HVAC_MODE_AUTO,
    CONF_HVAC_MODE_COOL,
    CONF_HVAC_MODE_DRY,
    CONF_HVAC_MODE_FAN_ONLY,
    CONF_HVAC_MODE_HEAT,
    CONF_HVAC_MODE_HEAT_COOL,
    CONF_HVAC_MODE_OFF,
    CONF_HVAC_MODE_REGISTER,
    CONF_HVAC_MODE_VALUES,
    CONF_HVAC_OFF_VALUE,
    CONF_HVAC_ON_VALUE,
    CONF_HVAC_ONOFF_COIL,
    CONF_HVAC_ONOFF_REGISTER,
    CONF_INPUT_TYPE,
    CONF_MAX_TEMP,
    CONF_MAX_VALUE,
    CONF_MIN_TEMP,
    CONF_MIN_VALUE,
    CONF_MSG_WAIT,
    CONF_NAN_VALUE,
    CONF_PARITY,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_SLAVE_COUNT,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    CONF_STEP,
    CONF_STOPBITS,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_SWING_MODE_REGISTER,
    CONF_SWING_MODE_SWING_BOTH,
    CONF_SWING_MODE_SWING_HORIZ,
    CONF_SWING_MODE_SWING_OFF,
    CONF_SWING_MODE_SWING_ON,
    CONF_SWING_MODE_SWING_VERT,
    CONF_SWING_MODE_VALUES,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_OFFSET,
    CONF_TARGET_TEMP_SCALE,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_VERIFY,
    CONF_VIRTUAL_COUNT,
    CONF_WRITE_REGISTERS,
    CONF_WRITE_TYPE,
    CONF_ZERO_SUPPRESS,
    DEFAULT_HUB,
    DEFAULT_HVAC_OFF_VALUE,
    DEFAULT_HVAC_ON_VALUE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMP_UNIT,
    DOMAIN,
    RTUOVERTCP,
    SERIAL,
    TCP,
    UDP,
    DataType,
)
from .validators import (
    duplicate_fan_mode_validator,
    duplicate_swing_mode_validator,
    ensure_and_check_conflicting_scales_and_offsets,
    hvac_fixedsize_reglist_validator,
    nan_validator,
    not_zero_value,
    register_int_list_validator,
    struct_validator,
)

BASE_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string}
)


BASE_COMPONENT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.string,
        probatio.Required(CONF_ADDRESS): cv.positive_int,
        probatio.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        probatio.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


BASE_STRUCT_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        probatio.Optional(
            CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING
        ): probatio.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        probatio.Optional(CONF_COUNT): cv.positive_int,
        probatio.Optional(CONF_DATA_TYPE, default=DataType.INT16): probatio.In(
            [
                DataType.INT16,
                DataType.INT32,
                DataType.INT64,
                DataType.UINT16,
                DataType.UINT32,
                DataType.UINT64,
                DataType.FLOAT16,
                DataType.FLOAT32,
                DataType.FLOAT64,
                DataType.STRING,
                DataType.CUSTOM,
            ]
        ),
        probatio.Optional(CONF_STRUCTURE): cv.string,
        probatio.Optional(CONF_SCALE): probatio.All(
            probatio.Coerce(float), lambda v: not_zero_value(v, "Scale cannot be zero.")
        ),
        probatio.Optional(CONF_OFFSET): probatio.Coerce(float),
        probatio.Optional(CONF_PRECISION): cv.positive_int,
        probatio.Optional(
            CONF_SWAP,
        ): probatio.In(
            [
                CONF_SWAP_BYTE,
                CONF_SWAP_WORD,
                CONF_SWAP_WORD_BYTE,
            ]
        ),
    }
)


BASE_SWITCH_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        probatio.Optional(
            CONF_WRITE_TYPE, default=CALL_TYPE_REGISTER_HOLDING
        ): probatio.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_COIL,
                CALL_TYPE_X_COILS,
                CALL_TYPE_X_REGISTER_HOLDINGS,
            ]
        ),
        probatio.Optional(CONF_COMMAND_OFF, default=0x00): cv.positive_int,
        probatio.Optional(CONF_COMMAND_ON, default=0x01): cv.positive_int,
        probatio.Optional(CONF_VERIFY): probatio.Maybe(
            {
                probatio.Optional(CONF_ADDRESS): cv.positive_int,
                probatio.Optional(CONF_INPUT_TYPE): probatio.In(
                    [
                        CALL_TYPE_REGISTER_HOLDING,
                        CALL_TYPE_DISCRETE,
                        CALL_TYPE_REGISTER_INPUT,
                        CALL_TYPE_COIL,
                        CALL_TYPE_X_COILS,
                        CALL_TYPE_X_REGISTER_HOLDINGS,
                    ]
                ),
                probatio.Optional(CONF_STATE_OFF): probatio.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                probatio.Optional(CONF_STATE_ON): probatio.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                probatio.Optional(CONF_DELAY, default=0): cv.positive_int,
            }
        ),
    }
)


CLIMATE_SCHEMA = probatio.All(
    BASE_STRUCT_SCHEMA.extend(
        {
            probatio.Required(CONF_TARGET_TEMP): hvac_fixedsize_reglist_validator,
            probatio.Optional(
                CONF_TARGET_TEMP_WRITE_REGISTERS, default=False
            ): cv.boolean,
            probatio.Optional(CONF_MAX_TEMP, default=35): probatio.Coerce(int),
            probatio.Optional(CONF_MIN_TEMP, default=5): probatio.Coerce(int),
            probatio.Optional(CONF_STEP, default=0.5): probatio.Coerce(float),
            probatio.Optional(
                CONF_TEMPERATURE_UNIT, default=DEFAULT_TEMP_UNIT
            ): cv.string,
            probatio.Exclusive(
                CONF_HVAC_ONOFF_COIL, "hvac_onoff_type"
            ): cv.positive_int,
            probatio.Exclusive(
                CONF_HVAC_ONOFF_REGISTER, "hvac_onoff_type"
            ): cv.positive_int,
            probatio.Optional(CONF_CURRENT_TEMP_SCALE): probatio.All(
                probatio.Coerce(float),
                lambda v: not_zero_value(
                    v, "Current temperature scale cannot be zero."
                ),
            ),
            probatio.Optional(CONF_TARGET_TEMP_SCALE): probatio.All(
                probatio.Coerce(float),
                lambda v: not_zero_value(v, "Target temperature scale cannot be zero."),
            ),
            probatio.Optional(CONF_CURRENT_TEMP_OFFSET): probatio.Coerce(float),
            probatio.Optional(CONF_TARGET_TEMP_OFFSET): probatio.Coerce(float),
            probatio.Optional(
                CONF_HVAC_ON_VALUE, default=DEFAULT_HVAC_ON_VALUE
            ): cv.positive_int,
            probatio.Optional(
                CONF_HVAC_OFF_VALUE, default=DEFAULT_HVAC_OFF_VALUE
            ): cv.positive_int,
            probatio.Optional(CONF_WRITE_REGISTERS, default=False): cv.boolean,
            probatio.Optional(CONF_HVAC_MODE_REGISTER): probatio.Maybe(
                {
                    CONF_ADDRESS: cv.positive_int,
                    CONF_HVAC_MODE_VALUES: {
                        probatio.Optional(CONF_HVAC_MODE_OFF): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_HEAT): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_COOL): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_HEAT_COOL): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_AUTO): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_DRY): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_MODE_FAN_ONLY): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                    },
                    probatio.Optional(CONF_WRITE_REGISTERS, default=False): cv.boolean,
                }
            ),
            probatio.Optional(CONF_HVAC_ACTION_REGISTER): probatio.Maybe(
                {
                    CONF_ADDRESS: cv.positive_int,
                    CONF_HVAC_ACTION_VALUES: {
                        probatio.Optional(CONF_HVAC_ACTION_COOLING): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_DEFROSTING): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_DRYING): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_FAN): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_HEATING): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_IDLE): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_OFF): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                        probatio.Optional(CONF_HVAC_ACTION_PREHEATING): probatio.Any(
                            cv.positive_int, [cv.positive_int]
                        ),
                    },
                    probatio.Optional(
                        CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING
                    ): probatio.In(
                        [
                            CALL_TYPE_REGISTER_HOLDING,
                            CALL_TYPE_REGISTER_INPUT,
                        ]
                    ),
                }
            ),
            probatio.Optional(CONF_FAN_MODE_REGISTER): probatio.Maybe(
                probatio.All(
                    {
                        probatio.Required(CONF_ADDRESS): register_int_list_validator,
                        CONF_FAN_MODE_VALUES: {
                            probatio.Optional(CONF_FAN_MODE_ON): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_OFF): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_AUTO): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_LOW): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_MEDIUM): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_HIGH): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_TOP): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_MIDDLE): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_FOCUS): cv.positive_int,
                            probatio.Optional(CONF_FAN_MODE_DIFFUSE): cv.positive_int,
                        },
                    },
                    duplicate_fan_mode_validator,
                ),
            ),
            probatio.Optional(CONF_SWING_MODE_REGISTER): probatio.Maybe(
                probatio.All(
                    {
                        probatio.Required(CONF_ADDRESS): register_int_list_validator,
                        CONF_SWING_MODE_VALUES: {
                            probatio.Optional(
                                CONF_SWING_MODE_SWING_ON
                            ): cv.positive_int,
                            probatio.Optional(
                                CONF_SWING_MODE_SWING_OFF
                            ): cv.positive_int,
                            probatio.Optional(
                                CONF_SWING_MODE_SWING_HORIZ
                            ): cv.positive_int,
                            probatio.Optional(
                                CONF_SWING_MODE_SWING_VERT
                            ): cv.positive_int,
                            probatio.Optional(
                                CONF_SWING_MODE_SWING_BOTH
                            ): cv.positive_int,
                        },
                    },
                    duplicate_swing_mode_validator,
                )
            ),
        },
    ),
    ensure_and_check_conflicting_scales_and_offsets,
)

COVERS_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        probatio.Optional(
            CONF_INPUT_TYPE,
            default=CALL_TYPE_REGISTER_HOLDING,
        ): probatio.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_COIL,
            ]
        ),
        probatio.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_STATE_CLOSED, default=0): cv.positive_int,
        probatio.Optional(CONF_STATE_CLOSING, default=3): cv.positive_int,
        probatio.Optional(CONF_STATE_OPEN, default=1): cv.positive_int,
        probatio.Optional(CONF_STATE_OPENING, default=2): cv.positive_int,
        probatio.Optional(CONF_STATUS_REGISTER): cv.positive_int,
        probatio.Optional(
            CONF_STATUS_REGISTER_TYPE,
            default=CALL_TYPE_REGISTER_HOLDING,
        ): probatio.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
    }
)

SWITCH_SCHEMA = BASE_SWITCH_SCHEMA.extend(
    {
        probatio.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
    }
)

LIGHT_SCHEMA = BASE_SWITCH_SCHEMA.extend(
    {
        probatio.Optional(CONF_BRIGHTNESS_REGISTER): cv.positive_int,
        probatio.Optional(CONF_COLOR_TEMP_REGISTER): cv.positive_int,
        probatio.Optional(CONF_MIN_TEMP): cv.positive_int,
        probatio.Optional(CONF_MAX_TEMP): cv.positive_int,
    }
)

FAN_SCHEMA = BASE_SWITCH_SCHEMA.extend({})

SENSOR_SCHEMA = probatio.All(
    BASE_STRUCT_SCHEMA.extend(
        {
            probatio.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
            probatio.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            probatio.Exclusive(CONF_VIRTUAL_COUNT, "vir_sen_count"): cv.positive_int,
            probatio.Exclusive(CONF_SLAVE_COUNT, "vir_sen_count"): cv.positive_int,
            probatio.Optional(CONF_MIN_VALUE): probatio.Coerce(float),
            probatio.Optional(CONF_MAX_VALUE): probatio.Coerce(float),
            probatio.Optional(CONF_NAN_VALUE): nan_validator,
            probatio.Optional(CONF_ZERO_SUPPRESS): cv.positive_float,
        }
    ),
)

BINARY_SENSOR_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        probatio.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_COIL): probatio.In(
            [
                CALL_TYPE_COIL,
                CALL_TYPE_DISCRETE,
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        probatio.Exclusive(CONF_VIRTUAL_COUNT, "vir_bin_count"): cv.positive_int,
        probatio.Exclusive(CONF_SLAVE_COUNT, "vir_bin_count"): cv.positive_int,
    }
)

MODBUS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string,
        probatio.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        probatio.Optional(CONF_DELAY, default=0): cv.positive_int,
        probatio.Optional(CONF_MSG_WAIT): cv.positive_int,
        probatio.Optional(CONF_BINARY_SENSORS): probatio.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
        probatio.Optional(CONF_CLIMATES): probatio.All(
            cv.ensure_list, [probatio.All(CLIMATE_SCHEMA, struct_validator)]
        ),
        probatio.Optional(CONF_COVERS): probatio.All(cv.ensure_list, [COVERS_SCHEMA]),
        probatio.Optional(CONF_LIGHTS): probatio.All(cv.ensure_list, [LIGHT_SCHEMA]),
        probatio.Optional(CONF_SENSORS): probatio.All(
            cv.ensure_list, [probatio.All(SENSOR_SCHEMA, struct_validator)]
        ),
        probatio.Optional(CONF_SWITCHES): probatio.All(cv.ensure_list, [SWITCH_SCHEMA]),
        probatio.Optional(CONF_FANS): probatio.All(cv.ensure_list, [FAN_SCHEMA]),
    },
    extra=probatio.ALLOW_EXTRA,
)

SERIAL_SCHEMA = MODBUS_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): SERIAL,
        probatio.Required(CONF_BAUDRATE): cv.positive_int,
        probatio.Required(CONF_BYTESIZE): probatio.Any(5, 6, 7, 8),
        probatio.Required(CONF_METHOD): probatio.Any("rtu", "ascii"),
        probatio.Required(CONF_PORT): cv.string,
        probatio.Required(CONF_PARITY): probatio.Any("E", "O", "N"),
        probatio.Required(CONF_STOPBITS): probatio.Any(1, 2),
    }
)

ETHERNET_SCHEMA = MODBUS_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_PORT): cv.port,
        probatio.Required(CONF_TYPE): probatio.Any(TCP, UDP, RTUOVERTCP),
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            cv.ensure_list,
            [
                probatio.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA),
            ],
        ),
    },
    extra=probatio.ALLOW_EXTRA,
)

# Per-platform schema for a single entity config, used to validate the entity
# lists stored in a device subentry.
PLATFORM_SCHEMAS: dict[Platform, VolSchemaType] = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMA,
    Platform.CLIMATE: probatio.All(CLIMATE_SCHEMA, struct_validator),
    Platform.COVER: COVERS_SCHEMA,
    Platform.FAN: FAN_SCHEMA,
    Platform.LIGHT: LIGHT_SCHEMA,
    Platform.SENSOR: probatio.All(SENSOR_SCHEMA, struct_validator),
    Platform.SWITCH: SWITCH_SCHEMA,
}
