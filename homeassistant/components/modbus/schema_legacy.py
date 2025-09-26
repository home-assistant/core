"""Support for Modbus."""

from __future__ import annotations

from collections import namedtuple
import logging
import struct
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.climate import HVACMode
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

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
    MODBUS_DOMAIN as DOMAIN,
    PLATFORMS,
    RTUOVERTCP,
    SERIAL,
    TCP,
    UDP,
    DataType,
)

_LOGGER = logging.getLogger(__name__)

ENTRY = namedtuple(  # noqa: PYI024
    "ENTRY",
    [
        "struct_id",
        "register_count",
        "validate_parm",
    ],
)


ILLEGAL = "I"
OPTIONAL = "O"
DEMANDED = "D"

PARM_IS_LEGAL = namedtuple(  # noqa: PYI024
    "PARM_IS_LEGAL",
    [
        "count",
        "structure",
        "slave_count",
        "swap_byte",
        "swap_word",
    ],
)
DEFAULT_STRUCT_FORMAT = {
    DataType.INT16: ENTRY(
        "h", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.UINT16: ENTRY(
        "H", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.FLOAT16: ENTRY(
        "e", 1, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, ILLEGAL)
    ),
    DataType.INT32: ENTRY(
        "i", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.UINT32: ENTRY(
        "I", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.FLOAT32: ENTRY(
        "f", 2, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.INT64: ENTRY(
        "q", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.UINT64: ENTRY(
        "Q", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.FLOAT64: ENTRY(
        "d", 4, PARM_IS_LEGAL(ILLEGAL, ILLEGAL, OPTIONAL, OPTIONAL, OPTIONAL)
    ),
    DataType.STRING: ENTRY(
        "s", 0, PARM_IS_LEGAL(DEMANDED, ILLEGAL, ILLEGAL, OPTIONAL, ILLEGAL)
    ),
    DataType.CUSTOM: ENTRY(
        "?", 0, PARM_IS_LEGAL(DEMANDED, DEMANDED, ILLEGAL, ILLEGAL, ILLEGAL)
    ),
}


def modbus_create_issue(
    hass: HomeAssistant, key: str, subs: list[str], err: str
) -> None:
    """Create issue modbus style."""
    async_create_issue(
        hass,
        DOMAIN,
        key,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=key,
        translation_placeholders={
            "sub_1": subs[0],
            "sub_2": subs[1],
            "sub_3": subs[2],
            "integration": DOMAIN,
        },
        issue_domain=DOMAIN,
        learn_more_url="https://www.home-assistant.io/integrations/modbus",
    )
    _LOGGER.warning(err)


def struct_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Sensor schema validator."""

    name = config[CONF_NAME]
    data_type = config[CONF_DATA_TYPE]
    if data_type == "int":
        data_type = config[CONF_DATA_TYPE] = DataType.INT16
    count = config.get(CONF_COUNT)
    structure = config.get(CONF_STRUCTURE)
    slave_count = config.get(CONF_SLAVE_COUNT, config.get(CONF_VIRTUAL_COUNT))
    validator = DEFAULT_STRUCT_FORMAT[data_type].validate_parm
    swap_type = config.get(CONF_SWAP)
    swap_dict = {
        CONF_SWAP_BYTE: validator.swap_byte,
        CONF_SWAP_WORD: validator.swap_word,
        CONF_SWAP_WORD_BYTE: validator.swap_word,
    }
    swap_type_validator = swap_dict[swap_type] if swap_type else OPTIONAL
    for entry in (
        (count, validator.count, CONF_COUNT),
        (structure, validator.structure, CONF_STRUCTURE),
        (
            slave_count,
            validator.slave_count,
            f"{CONF_VIRTUAL_COUNT} / {CONF_SLAVE_COUNT}:",
        ),
        (swap_type, swap_type_validator, f"{CONF_SWAP}:{swap_type}"),
    ):
        if entry[0] is None:
            if entry[1] == DEMANDED:
                error = f"{name}: `{entry[2]}` missing, demanded with `{CONF_DATA_TYPE}: {data_type}`"
                raise vol.Invalid(error)
        elif entry[1] == ILLEGAL:
            error = f"{name}: `{entry[2]}` illegal with `{CONF_DATA_TYPE}: {data_type}`"
            raise vol.Invalid(error)

    if config[CONF_DATA_TYPE] == DataType.CUSTOM:
        assert isinstance(structure, str)
        assert isinstance(count, int)
        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            raise vol.Invalid(f"{name}: error in structure format --> {err!s}") from err
        bytecount = count * 2
        if bytecount != size:
            raise vol.Invalid(
                f"{name}: Size of structure is {size} bytes but `{CONF_COUNT}: {count}` is {bytecount} bytes"
            )
    else:
        if data_type != DataType.STRING:
            config[CONF_COUNT] = DEFAULT_STRUCT_FORMAT[data_type].register_count
        if slave_count:
            structure = (
                f">{slave_count + 1}{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
            )
        else:
            structure = f">{DEFAULT_STRUCT_FORMAT[data_type].struct_id}"
    return {
        **config,
        CONF_STRUCTURE: structure,
        CONF_SWAP: swap_type,
    }


def hvac_fixedsize_reglist_validator(value: Any) -> list:
    """Check the number of registers for target temp. and coerce it to a list, if valid."""
    if isinstance(value, int):
        value = [value] * len(HVACMode)
        return list(value)

    if len(value) == len(HVACMode):
        _rv = True
        for svalue in value:
            if isinstance(svalue, int) is False:
                _rv = False
                break
        if _rv is True:
            return list(value)

    raise vol.Invalid(
        f"Invalid target temp register. Required type: integer, allowed 1 or list of {len(HVACMode)} registers"
    )


def nan_validator(value: Any) -> int:
    """Convert nan string to number (can be hex string or int)."""
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return int(value, 16)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(f"invalid number {value}") from err


def duplicate_fan_mode_validator(config: dict[str, Any]) -> dict:
    """Control modbus climate fan mode values for duplicates."""
    fan_modes: set[int] = set()
    errors = []
    for key, value in config[CONF_FAN_MODE_VALUES].items():
        if value in fan_modes:
            warn = f"Modbus fan mode {key} has a duplicate value {value}, not loaded, values must be unique!"
            _LOGGER.warning(warn)
            errors.append(key)
        else:
            fan_modes.add(value)

    for key in reversed(errors):
        del config[CONF_FAN_MODE_VALUES][key]
    return config


def duplicate_swing_mode_validator(config: dict[str, Any]) -> dict:
    """Control modbus climate swing mode values for duplicates."""
    swing_modes: set[int] = set()
    errors = []
    for key, value in config[CONF_SWING_MODE_VALUES].items():
        if value in swing_modes:
            warn = f"Modbus swing mode {key} has a duplicate value {value}, not loaded, values must be unique!"
            _LOGGER.warning(warn)
            errors.append(key)
        else:
            swing_modes.add(value)

    for key in reversed(errors):
        del config[CONF_SWING_MODE_VALUES][key]
    return config


def register_int_list_validator(value: Any) -> Any:
    """Check if a register (CONF_ADRESS) is an int or a list having only 1 register."""
    if isinstance(value, int) and value >= 0:
        return value

    if isinstance(value, list):
        if (len(value) == 1) and isinstance(value[0], int) and value[0] >= 0:
            return value

    raise vol.Invalid(
        f"Invalid {CONF_ADDRESS} register for fan/swing mode. Required type: positive integer, allowed 1 or list of 1 register."
    )


def validate_modbus(
    hass: HomeAssistant,
    hosts: set[str],
    hub_names: set[str],
    hub: dict,
    hub_name_inx: int,
) -> bool:
    """Validate modbus entries."""
    host: str = (
        hub[CONF_PORT]
        if hub[CONF_TYPE] == SERIAL
        else f"{hub[CONF_HOST]}_{hub[CONF_PORT]}"
    )
    if CONF_NAME not in hub:
        hub[CONF_NAME] = (
            DEFAULT_HUB if not hub_name_inx else f"{DEFAULT_HUB}_{hub_name_inx}"
        )
        hub_name_inx += 1
        modbus_create_issue(
            hass,
            "missing_modbus_name",
            [
                "name",
                host,
                hub[CONF_NAME],
            ],
            f"Modbus host/port {host} is missing name, added {hub[CONF_NAME]}!",
        )
    name = hub[CONF_NAME]
    if host in hosts or name in hub_names:
        modbus_create_issue(
            hass,
            "duplicate_modbus_entry",
            [
                host,
                hub[CONF_NAME],
                "",
            ],
            f"Modbus {name} host/port {host} is duplicate, not loaded!",
        )
        return False
    hosts.add(host)
    hub_names.add(name)
    return True


def validate_entity(
    hass: HomeAssistant,
    hub_name: str,
    component: str,
    entity: dict,
    minimum_scan_interval: int,
    ent_names: set[str],
    ent_addr: set[str],
) -> bool:
    """Validate entity."""
    name = f"{component}.{entity[CONF_NAME]}"
    scan_interval = entity.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if 0 < scan_interval < 5:
        err = (
            f"{hub_name} {name} scan_interval is lower than 5 seconds, "
            "which may cause Home Assistant stability issues"
        )
        _LOGGER.warning(err)
    entity[CONF_SCAN_INTERVAL] = scan_interval
    minimum_scan_interval = min(scan_interval, minimum_scan_interval)
    if name in ent_names:
        modbus_create_issue(
            hass,
            "duplicate_entity_name",
            [
                f"{hub_name}/{name}",
                "",
                "",
            ],
            f"Modbus {hub_name}/{name} is duplicate, second entry not loaded!",
        )
        return False
    ent_names.add(name)
    return True


def check_config(hass: HomeAssistant, config: dict) -> dict:
    """Do final config check."""
    hosts: set[str] = set()
    hub_names: set[str] = set()
    hub_name_inx = 0
    minimum_scan_interval = 0
    ent_names: set[str] = set()
    ent_addr: set[str] = set()

    hub_inx = 0
    while hub_inx < len(config):
        hub = config[hub_inx]
        if not validate_modbus(hass, hosts, hub_names, hub, hub_name_inx):
            del config[hub_inx]
            continue
        minimum_scan_interval = 9999
        no_entities = True
        for component, conf_key in PLATFORMS:
            if conf_key not in hub:
                continue
            no_entities = False
            entity_inx = 0
            entities = hub[conf_key]
            while entity_inx < len(entities):
                if not validate_entity(
                    hass,
                    hub[CONF_NAME],
                    component,
                    entities[entity_inx],
                    minimum_scan_interval,
                    ent_names,
                    ent_addr,
                ):
                    del entities[entity_inx]
                else:
                    entity_inx += 1
        if no_entities:
            modbus_create_issue(
                hass,
                "no_entities",
                [
                    hub[CONF_NAME],
                    "",
                    "",
                ],
                f"Modbus {hub[CONF_NAME]} contain no entities, causing instability, entry not loaded",
            )
            del config[hub_inx]
            continue
        if hub[CONF_TIMEOUT] >= minimum_scan_interval:
            hub[CONF_TIMEOUT] = minimum_scan_interval - 1
            _LOGGER.warning(
                "Modbus %s timeout is adjusted(%d) due to scan_interval",
                hub[CONF_NAME],
                hub[CONF_TIMEOUT],
            )
        hub_inx += 1
    return config


CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        vol.Optional(CONF_COUNT): cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DataType.INT16): vol.In(
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
        vol.Optional(CONF_STRUCTURE): cv.string,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): cv.positive_int,
        vol.Optional(
            CONF_SWAP,
        ): vol.In(
            [
                CONF_SWAP_BYTE,
                CONF_SWAP_WORD,
                CONF_SWAP_WORD_BYTE,
            ]
        ),
        vol.Required(CONF_TARGET_TEMP): hvac_fixedsize_reglist_validator,
        vol.Optional(CONF_TARGET_TEMP_WRITE_REGISTERS, default=False): cv.boolean,
        vol.Optional(CONF_MAX_TEMP, default=35): vol.Coerce(int),
        vol.Optional(CONF_MIN_TEMP, default=5): vol.Coerce(int),
        vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
        vol.Optional(CONF_TEMPERATURE_UNIT, default=DEFAULT_TEMP_UNIT): cv.string,
        vol.Exclusive(CONF_HVAC_ONOFF_COIL, "hvac_onoff_type"): cv.positive_int,
        vol.Exclusive(CONF_HVAC_ONOFF_REGISTER, "hvac_onoff_type"): cv.positive_int,
        vol.Optional(
            CONF_HVAC_ON_VALUE, default=DEFAULT_HVAC_ON_VALUE
        ): cv.positive_int,
        vol.Optional(
            CONF_HVAC_OFF_VALUE, default=DEFAULT_HVAC_OFF_VALUE
        ): cv.positive_int,
        vol.Optional(CONF_WRITE_REGISTERS, default=False): cv.boolean,
        vol.Optional(CONF_HVAC_MODE_REGISTER): vol.Maybe(
            {
                CONF_ADDRESS: cv.positive_int,
                CONF_HVAC_MODE_VALUES: {
                    vol.Optional(CONF_HVAC_MODE_OFF): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_HEAT): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_COOL): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_HEAT_COOL): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_AUTO): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_DRY): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_MODE_FAN_ONLY): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                },
                vol.Optional(CONF_WRITE_REGISTERS, default=False): cv.boolean,
            }
        ),
        vol.Optional(CONF_HVAC_ACTION_REGISTER): vol.Maybe(
            {
                CONF_ADDRESS: cv.positive_int,
                CONF_HVAC_ACTION_VALUES: {
                    vol.Optional(CONF_HVAC_ACTION_COOLING): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_DEFROSTING): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_DRYING): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_FAN): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_HEATING): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_IDLE): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_OFF): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                    vol.Optional(CONF_HVAC_ACTION_PREHEATING): vol.Any(
                        cv.positive_int, [cv.positive_int]
                    ),
                },
                vol.Optional(
                    CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING
                ): vol.In(
                    [
                        CALL_TYPE_REGISTER_HOLDING,
                        CALL_TYPE_REGISTER_INPUT,
                    ]
                ),
            }
        ),
        vol.Optional(CONF_FAN_MODE_REGISTER): vol.Maybe(
            vol.All(
                {
                    vol.Required(CONF_ADDRESS): register_int_list_validator,
                    CONF_FAN_MODE_VALUES: {
                        vol.Optional(CONF_FAN_MODE_ON): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_OFF): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_AUTO): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_LOW): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_MEDIUM): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_HIGH): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_TOP): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_MIDDLE): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_FOCUS): cv.positive_int,
                        vol.Optional(CONF_FAN_MODE_DIFFUSE): cv.positive_int,
                    },
                },
                duplicate_fan_mode_validator,
            ),
        ),
        vol.Optional(CONF_SWING_MODE_REGISTER): vol.Maybe(
            vol.All(
                {
                    vol.Required(CONF_ADDRESS): register_int_list_validator,
                    CONF_SWING_MODE_VALUES: {
                        vol.Optional(CONF_SWING_MODE_SWING_ON): cv.positive_int,
                        vol.Optional(CONF_SWING_MODE_SWING_OFF): cv.positive_int,
                        vol.Optional(CONF_SWING_MODE_SWING_HORIZ): cv.positive_int,
                        vol.Optional(CONF_SWING_MODE_SWING_VERT): cv.positive_int,
                        vol.Optional(CONF_SWING_MODE_SWING_BOTH): cv.positive_int,
                    },
                },
                duplicate_swing_mode_validator,
            )
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

COVERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(
            CONF_INPUT_TYPE,
            default=CALL_TYPE_REGISTER_HOLDING,
        ): vol.In(
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
    },
    extra=vol.ALLOW_EXTRA,
)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
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
                vol.Optional(CONF_STATE_OFF): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_STATE_ON): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional(CONF_DELAY, default=0): cv.positive_int,
            }
        ),
        vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
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
                vol.Optional(CONF_STATE_OFF): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_STATE_ON): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional(CONF_DELAY, default=0): cv.positive_int,
            }
        ),
        vol.Optional(CONF_BRIGHTNESS_REGISTER): cv.positive_int,
        vol.Optional(CONF_COLOR_TEMP_REGISTER): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP): cv.positive_int,
        vol.Optional(CONF_MAX_TEMP): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)

FAN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
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
                vol.Optional(CONF_STATE_OFF): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_STATE_ON): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional(CONF_DELAY, default=0): cv.positive_int,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        vol.Optional(CONF_COUNT): cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DataType.INT16): vol.In(
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
        vol.Optional(CONF_STRUCTURE): cv.string,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): cv.positive_int,
        vol.Optional(
            CONF_SWAP,
        ): vol.In(
            [
                CONF_SWAP_BYTE,
                CONF_SWAP_WORD,
                CONF_SWAP_WORD_BYTE,
            ]
        ),
        vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Exclusive(CONF_VIRTUAL_COUNT, "vir_sen_count"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE_COUNT, "vir_sen_count"): cv.positive_int,
        vol.Optional(CONF_MIN_VALUE): vol.Coerce(float),
        vol.Optional(CONF_MAX_VALUE): vol.Coerce(float),
        vol.Optional(CONF_NAN_VALUE): nan_validator,
        vol.Optional(CONF_ZERO_SUPPRESS): cv.positive_float,
    },
    extra=vol.ALLOW_EXTRA,
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.positive_int,
        vol.Exclusive(CONF_DEVICE_ADDRESS, "slave_addr"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE, "slave_addr"): cv.positive_int,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_INPUT_TYPE, default=CALL_TYPE_COIL): vol.In(
            [
                CALL_TYPE_COIL,
                CALL_TYPE_DISCRETE,
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_REGISTER_INPUT,
            ]
        ),
        vol.Exclusive(CONF_VIRTUAL_COUNT, "vir_bin_count"): cv.positive_int,
        vol.Exclusive(CONF_SLAVE_COUNT, "vir_bin_count"): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)


def validate_modbus_schema(config: dict[str, Any]) -> dict:
    """Control modbus connection."""
    if config[CONF_TYPE] == SERIAL:
        if CONF_HOST in config:
            raise vol.Invalid(f"{CONF_HOST}: {config[CONF_HOST]} not allowed.")
        for key in (
            CONF_BAUDRATE,
            CONF_BYTESIZE,
            CONF_METHOD,
            CONF_PARITY,
            CONF_STOPBITS,
        ):
            if key not in config:
                raise vol.Invalid(f"{key}: is required.")
        if not isinstance(config[CONF_PORT], str):
            raise vol.Invalid(f"{CONF_PORT}: {key} must be string.")
        return config
    if CONF_HOST not in config:
        raise vol.Invalid(f"{CONF_HOST}: {config[CONF_HOST]} is required.")
    for key in (CONF_BAUDRATE, CONF_BYTESIZE, CONF_METHOD, CONF_PARITY, CONF_STOPBITS):
        if key in config:
            raise vol.Invalid(f"{key}: {config[key]} not allowed.")
        if not isinstance(config[CONF_PORT], int):
            raise vol.Invalid(f"{CONF_PORT}: {key} must be integer.")
    return config


MODBUS_SCHEMA = vol.All(
    {
        vol.Required(CONF_TYPE): vol.Any(SERIAL, TCP, UDP, RTUOVERTCP),
        vol.Required(CONF_PORT): vol.Any(cv.port, cv.string),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
        vol.Optional(CONF_METHOD): vol.Any("rtu", "ascii"),
        vol.Optional(CONF_PARITY): vol.Any("E", "O", "N"),
        vol.Optional(CONF_STOPBITS): vol.Any(1, 2),
        vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        vol.Optional(CONF_DELAY, default=0): cv.positive_int,
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
    },
    validate_modbus_schema,
)

CONFIG_SCHEMA_LEGACY = vol.All(
    cv.ensure_list,
    [MODBUS_SCHEMA],
)
