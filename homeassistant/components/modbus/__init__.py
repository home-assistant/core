"""Support for Modbus."""
from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol

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
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_STATE,
    ATTR_UNIT,
    ATTR_VALUE,
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_X_COILS,
    CALL_TYPE_X_REGISTER_HOLDINGS,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CLIMATES,
    CONF_CLOSE_COMM_ON_ERROR,
    CONF_DATA_COUNT,
    CONF_DATA_TYPE,
    CONF_FANS,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_MSG_WAIT,
    CONF_PARITY,
    CONF_PRECISION,
    CONF_RETRIES,
    CONF_RETRY_ON_EMPTY,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
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
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_TARGET_TEMP,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_FLOAT16,
    DATA_TYPE_FLOAT32,
    DATA_TYPE_FLOAT64,
    DATA_TYPE_INT,
    DATA_TYPE_INT16,
    DATA_TYPE_INT32,
    DATA_TYPE_INT64,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
    DATA_TYPE_UINT16,
    DATA_TYPE_UINT32,
    DATA_TYPE_UINT64,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMP_UNIT,
    MODBUS_DOMAIN as DOMAIN,
    RTUOVERTCP,
    SERIAL,
    TCP,
    UDP,
)
from .modbus import ModbusHub, async_modbus_setup
from .validators import (
    duplicate_entity_validator,
    duplicate_modbus_validator,
    number_validator,
    scan_interval_validator,
    struct_validator,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string})


BASE_COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_LAZY_ERROR, default=0): cv.positive_int,
    }
)


BASE_STRUCT_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        vol.Optional(CONF_COUNT): cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT): vol.In(
            [
                DATA_TYPE_INT16,
                DATA_TYPE_INT32,
                DATA_TYPE_INT64,
                DATA_TYPE_UINT16,
                DATA_TYPE_UINT32,
                DATA_TYPE_UINT64,
                DATA_TYPE_FLOAT16,
                DATA_TYPE_FLOAT32,
                DATA_TYPE_FLOAT64,
                DATA_TYPE_STRING,
                DATA_TYPE_INT,
                DATA_TYPE_UINT,
                DATA_TYPE_FLOAT,
                DATA_TYPE_STRING,
                DATA_TYPE_CUSTOM,
            ]
        ),
        vol.Optional(CONF_STRUCTURE): cv.string,
        vol.Optional(CONF_SCALE, default=1): number_validator,
        vol.Optional(CONF_OFFSET, default=0): number_validator,
        vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
        vol.Optional(CONF_SWAP, default=CONF_SWAP_NONE): vol.In(
            [
                CONF_SWAP_NONE,
                CONF_SWAP_BYTE,
                CONF_SWAP_WORD,
                CONF_SWAP_WORD_BYTE,
            ]
        ),
    }
)


BASE_SWITCH_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        vol.Optional(CONF_WRITE_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_COIL,
                CALL_TYPE_X_COILS,
                CALL_TYPE_X_REGISTER_HOLDINGS,
            ]
        ),
        vol.Optional(CONF_COMMAND_OFF, default=0x00): cv.positive_int,
        vol.Optional(CONF_COMMAND_ON, default=0x01): cv.positive_int,
        vol.Optional(CONF_VERIFY): vol.Maybe(
            {
                vol.Optional(CONF_ADDRESS): cv.positive_int,
                vol.Optional(CONF_INPUT_TYPE): vol.In(
                    [
                        CALL_TYPE_REGISTER_HOLDING,
                        CALL_TYPE_DISCRETE,
                        CALL_TYPE_REGISTER_INPUT,
                        CALL_TYPE_COIL,
                        CALL_TYPE_X_COILS,
                        CALL_TYPE_X_REGISTER_HOLDINGS,
                    ]
                ),
                vol.Optional(CONF_STATE_OFF): cv.positive_int,
                vol.Optional(CONF_STATE_ON): cv.positive_int,
                vol.Optional(CONF_DELAY, default=0): cv.positive_int,
            }
        ),
    }
)


CLIMATE_SCHEMA = vol.All(
    cv.deprecated(CONF_DATA_COUNT, replacement_key=CONF_COUNT),
    BASE_STRUCT_SCHEMA.extend(
        {
            vol.Required(CONF_TARGET_TEMP): cv.positive_int,
            vol.Optional(CONF_MAX_TEMP, default=35): cv.positive_int,
            vol.Optional(CONF_MIN_TEMP, default=5): cv.positive_int,
            vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
            vol.Optional(CONF_TEMPERATURE_UNIT, default=DEFAULT_TEMP_UNIT): cv.string,
        }
    ),
)

COVERS_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING,): vol.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_COIL,
            ]
        ),
        vol.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLOSED, default=0): cv.positive_int,
        vol.Optional(CONF_STATE_CLOSING, default=3): cv.positive_int,
        vol.Optional(CONF_STATE_OPEN, default=1): cv.positive_int,
        vol.Optional(CONF_STATE_OPENING, default=2): cv.positive_int,
        vol.Optional(CONF_STATUS_REGISTER): cv.positive_int,
        vol.Optional(
            CONF_STATUS_REGISTER_TYPE,
            default=CALL_TYPE_REGISTER_HOLDING,
        ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
    }
)

SWITCH_SCHEMA = BASE_SWITCH_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
    }
)

LIGHT_SCHEMA = BASE_SWITCH_SCHEMA.extend({})

FAN_SCHEMA = BASE_SWITCH_SCHEMA.extend({})

SENSOR_SCHEMA = vol.All(
    cv.deprecated(CONF_REVERSE_ORDER),
    BASE_STRUCT_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_REVERSE_ORDER): cv.boolean,
        }
    ),
)

BINARY_SENSOR_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_COIL): vol.In(
            [CALL_TYPE_COIL, CALL_TYPE_DISCRETE]
        ),
    }
)

MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        vol.Optional(CONF_CLOSE_COMM_ON_ERROR, default=True): cv.boolean,
        vol.Optional(CONF_DELAY, default=0): cv.positive_int,
        vol.Optional(CONF_RETRIES, default=3): cv.positive_int,
        vol.Optional(CONF_RETRY_ON_EMPTY, default=False): cv.boolean,
        vol.Optional(CONF_MSG_WAIT): cv.positive_int,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_CLIMATES): vol.All(
            cv.ensure_list, [vol.All(CLIMATE_SCHEMA, struct_validator)]
        ),
        vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
        vol.Optional(CONF_LIGHTS): vol.All(cv.ensure_list, [LIGHT_SCHEMA]),
        vol.Optional(CONF_SENSORS): vol.All(
            cv.ensure_list, [vol.All(SENSOR_SCHEMA, struct_validator)]
        ),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
        vol.Optional(CONF_FANS): vol.All(cv.ensure_list, [FAN_SCHEMA]),
    }
)

SERIAL_SCHEMA = MODBUS_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERIAL,
        vol.Required(CONF_BAUDRATE): cv.positive_int,
        vol.Required(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
        vol.Required(CONF_METHOD): vol.Any("rtu", "ascii"),
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PARITY): vol.Any("E", "O", "N"),
        vol.Required(CONF_STOPBITS): vol.Any(1, 2),
    }
)

ETHERNET_SCHEMA = MODBUS_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TYPE): vol.Any(TCP, UDP, RTUOVERTCP),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            scan_interval_validator,
            duplicate_entity_validator,
            duplicate_modbus_validator,
            [
                vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA),
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Any(
            cv.positive_int, vol.All(cv.ensure_list, [cv.positive_int])
        ),
    }
)

SERVICE_WRITE_COIL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_STATE): vol.Any(
            cv.boolean, vol.All(cv.ensure_list, [cv.boolean])
        ),
    }
)
SERVICE_STOP_START_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_HUB): cv.string,
    }
)


def get_hub(hass: HomeAssistant, name: str) -> ModbusHub:
    """Return modbus hub with name."""
    return cast(ModbusHub, hass.data[DOMAIN][name])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Modbus component."""
    return await async_modbus_setup(
        hass,
        config,
        SERVICE_WRITE_REGISTER_SCHEMA,
        SERVICE_WRITE_COIL_SCHEMA,
        SERVICE_STOP_START_SCHEMA,
    )
