"""Validate Modbus configuration."""

from __future__ import annotations

from collections import namedtuple
import logging
import struct
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COUNT,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import (
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_FAN_MODE_REGISTER,
    CONF_FAN_MODE_VALUES,
    CONF_HVAC_MODE_REGISTER,
    CONF_HVAC_ONOFF_REGISTER,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_RETRIES,
    CONF_SLAVE_COUNT,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_SWING_MODE_REGISTER,
    CONF_SWING_MODE_VALUES,
    CONF_TARGET_TEMP,
    CONF_VIRTUAL_COUNT,
    CONF_WRITE_TYPE,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_DOMAIN as DOMAIN,
    PLATFORMS,
    SERIAL,
    DataType,
)

_LOGGER = logging.getLogger(__name__)

ENTRY = namedtuple(
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

PARM_IS_LEGAL = namedtuple(
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
            raise vol.Invalid(
                f"{name}: error in structure format --> {str(err)}"
            ) from err
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


def check_hvac_target_temp_registers(config: dict) -> dict:
    """Check conflicts among HVAC target temperature registers and HVAC ON/OFF, HVAC register, Fan Modes, Swing Modes."""

    if (
        CONF_HVAC_MODE_REGISTER in config
        and config[CONF_HVAC_MODE_REGISTER][CONF_ADDRESS] in config[CONF_TARGET_TEMP]
    ):
        wrn = f"{CONF_HVAC_MODE_REGISTER} overlaps CONF_TARGET_TEMP register(s). {CONF_HVAC_MODE_REGISTER} is not loaded!"
        _LOGGER.warning(wrn)
        del config[CONF_HVAC_MODE_REGISTER]
    if (
        CONF_HVAC_ONOFF_REGISTER in config
        and config[CONF_HVAC_ONOFF_REGISTER] in config[CONF_TARGET_TEMP]
    ):
        wrn = f"{CONF_HVAC_ONOFF_REGISTER} overlaps CONF_TARGET_TEMP register(s). {CONF_HVAC_ONOFF_REGISTER} is not loaded!"
        _LOGGER.warning(wrn)
        del config[CONF_HVAC_ONOFF_REGISTER]
    if (
        CONF_FAN_MODE_REGISTER in config
        and config[CONF_FAN_MODE_REGISTER][CONF_ADDRESS] in config[CONF_TARGET_TEMP]
    ):
        wrn = f"{CONF_FAN_MODE_REGISTER} overlaps CONF_TARGET_TEMP register(s). {CONF_FAN_MODE_REGISTER} is not loaded!"
        _LOGGER.warning(wrn)
        del config[CONF_FAN_MODE_REGISTER]

    if CONF_SWING_MODE_REGISTER in config:
        regToTest = (
            config[CONF_SWING_MODE_REGISTER][CONF_ADDRESS]
            if isinstance(config[CONF_SWING_MODE_REGISTER][CONF_ADDRESS], int)
            else config[CONF_SWING_MODE_REGISTER][CONF_ADDRESS][0]
        )
        if regToTest in config[CONF_TARGET_TEMP]:
            wrn = f"{CONF_SWING_MODE_REGISTER} overlaps CONF_TARGET_TEMP register(s). {CONF_SWING_MODE_REGISTER} is not loaded!"
            _LOGGER.warning(wrn)
            del config[CONF_SWING_MODE_REGISTER]

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
    if CONF_RETRIES in hub:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_retries",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_retries",
            translation_placeholders={
                "config_key": "retries",
                "integration": DOMAIN,
                "url": "https://www.home-assistant.io/integrations/modbus",
            },
        )
        _LOGGER.warning(
            "`retries`: is deprecated and will be removed in version 2024.7"
        )
    else:
        hub[CONF_RETRIES] = 3

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
    if CONF_LAZY_ERROR in entity:
        async_create_issue(
            hass,
            DOMAIN,
            "removed_lazy_error_count",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="removed_lazy_error_count",
            translation_placeholders={
                "config_key": "lazy_error_count",
                "integration": DOMAIN,
                "url": "https://www.home-assistant.io/integrations/modbus",
            },
        )
        _LOGGER.warning(
            "`lazy_error_count`: is deprecated and will be removed in version 2024.7"
        )
    name = f"{component}.{entity[CONF_NAME]}"
    addr = f"{hub_name}{entity[CONF_ADDRESS]}"
    scan_interval = entity.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if 0 < scan_interval < 5:
        err = (
            f"{hub_name} {name} scan_interval is lower than 5 seconds, "
            "which may cause Home Assistant stability issues"
        )
        _LOGGER.warning(err)
    entity[CONF_SCAN_INTERVAL] = scan_interval
    minimum_scan_interval = min(scan_interval, minimum_scan_interval)
    for conf_type in (
        CONF_INPUT_TYPE,
        CONF_WRITE_TYPE,
        CONF_COMMAND_ON,
        CONF_COMMAND_OFF,
    ):
        if conf_type in entity:
            addr += f"_{entity[conf_type]}"
    inx = entity.get(CONF_SLAVE) or entity.get(CONF_DEVICE_ADDRESS, 0)
    addr += f"_{inx}"
    loc_addr: set[str] = {addr}
    if CONF_TARGET_TEMP in entity:
        loc_addr.add(f"{hub_name}{entity[CONF_TARGET_TEMP]}_{inx}")
    if CONF_HVAC_MODE_REGISTER in entity:
        loc_addr.add(f"{hub_name}{entity[CONF_HVAC_MODE_REGISTER][CONF_ADDRESS]}_{inx}")
    if CONF_FAN_MODE_REGISTER in entity:
        loc_addr.add(f"{hub_name}{entity[CONF_FAN_MODE_REGISTER][CONF_ADDRESS]}_{inx}")
    if CONF_SWING_MODE_REGISTER in entity:
        loc_addr.add(
            f"{hub_name}{entity[CONF_SWING_MODE_REGISTER][CONF_ADDRESS]
                         if isinstance(entity[CONF_SWING_MODE_REGISTER][CONF_ADDRESS],int)
                         else entity[CONF_SWING_MODE_REGISTER][CONF_ADDRESS][0]}_{inx}"
        )

    dup_addrs = ent_addr.intersection(loc_addr)
    if len(dup_addrs) > 0:
        for addr in dup_addrs:
            modbus_create_issue(
                hass,
                "duplicate_entity_entry",
                [
                    f"{hub_name}/{name}",
                    addr,
                    "",
                ],
                f"Modbus {hub_name}/{name} address {addr} is duplicate, second entry not loaded!",
            )
        return False
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
    ent_addr.update(loc_addr)
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
