"""Support for Micropel."""
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA,
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_STATE,
    CONF_SWITCHES,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_VALUE,
    CONF_BIT_INDEX,
    CONF_CLIMATES,
    CONF_COMMUNICATOR_TYPE,
    CONF_CURRENT_TEMP_ADDRESS,
    CONF_DATA_TYPE,
    CONF_HUB,
    CONF_INPUT_TYPE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PLC,
    CONF_PRECISION,
    CONF_REGISTER_TYPE,
    CONF_SCALE,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    CONF_STEP,
    CONF_TARGET_TEMP_ADDRESS,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DEFAULT_HUB,
    DEFAULT_PLC,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REGISTER_TYPE_BIT,
    REGISTER_TYPE_LONG_WORD,
    REGISTER_TYPE_WORD,
)
from .micropel import micropel_setup

BASE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string})

BASE_PLATFORM_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_PLC, default=0): cv.positive_int,
    }
)

BINARY_SENSOR_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Required(CONF_BIT_INDEX): cv.positive_int,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)

SENSOR_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT): vol.In(
            [
                DATA_TYPE_INT,
                DATA_TYPE_FLOAT,
            ]
        ),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
        vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_WORD): vol.In(
            [REGISTER_TYPE_WORD, REGISTER_TYPE_LONG_WORD]
        ),
        vol.Optional(CONF_SCALE, default=1): cv.positive_float,
        vol.Optional(CONF_OFFSET, default=0): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

SWITCH_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Required(CONF_BIT_INDEX): cv.positive_int,
    }
)

CLIMATE_SCHEMA = BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.time_period, lambda value: value.total_seconds()
        ),
        vol.Required(CONF_TARGET_TEMP_ADDRESS): cv.positive_int,
        vol.Required(CONF_CURRENT_TEMP_ADDRESS): cv.positive_int,
        vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_WORD): vol.In(
            [REGISTER_TYPE_WORD, REGISTER_TYPE_LONG_WORD]
        ),
        vol.Optional(CONF_SCALE, default=1): cv.positive_float,
        vol.Optional(CONF_OFFSET, default=0): cv.string,
        vol.Optional(CONF_TEMPERATURE_UNIT): cv.string,
        vol.Optional(CONF_MAX_TEMP): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP): cv.positive_int,
        vol.Optional(CONF_STEP): cv.positive_int,
    }
)

COVERS_SCHEMA = vol.All(
    cv.has_at_least_one_key(REGISTER_TYPE_BIT, CONF_ADDRESS),
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                cv.time_period, lambda value: value.total_seconds()
            ),
            vol.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_PLC, default=DEFAULT_PLC): cv.positive_int,
            vol.Optional(CONF_STATE_CLOSED, default=0): cv.positive_int,
            vol.Optional(CONF_STATE_CLOSING, default=3): cv.positive_int,
            vol.Optional(CONF_STATE_OPEN, default=1): cv.positive_int,
            vol.Optional(CONF_STATE_OPENING, default=2): cv.positive_int,
            vol.Optional(CONF_STATUS_REGISTER): cv.positive_int,
            vol.Optional(
                CONF_STATUS_REGISTER_TYPE,
                default=REGISTER_TYPE_WORD,
            ): vol.In([REGISTER_TYPE_WORD, REGISTER_TYPE_LONG_WORD]),
            vol.Exclusive(REGISTER_TYPE_BIT, CONF_INPUT_TYPE): cv.positive_int,
            vol.Exclusive(CONF_ADDRESS, CONF_INPUT_TYPE): cv.positive_int,
        }
    ),
)

ETHERNET_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_COMMUNICATOR_TYPE): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_PASSWORD): cv.positive_int,
        vol.Optional(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATE_SCHEMA]),
        vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
        vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
    }
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_PLC): cv.positive_int,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Any(
            cv.positive_int, vol.All(cv.ensure_list, [cv.positive_int])
        ),
    }
)

SERVICE_WRITE_COIL_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_PLC): cv.positive_int,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Required(CONF_STATE): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Any(ETHERNET_SCHEMA),
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up Micropel component."""
    return micropel_setup(
        hass, config, SERVICE_WRITE_REGISTER_SCHEMA, SERVICE_WRITE_COIL_SCHEMA
    )
