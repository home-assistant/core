"""Validation helpers for KNX config schemas."""

from collections.abc import Callable
from enum import Enum
import ipaddress
import math
from typing import Any

import voluptuous as vol
from xknx.dpt import DPTBase, DPTNumeric, DPTString
from xknx.exceptions import CouldNotParseAddress
from xknx.telegram.address import IndividualAddress, parse_device_group_address

from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS as CONF_SENSOR_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    STATE_CLASS_UNITS,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_UNIT_OF_MEASUREMENT
from homeassistant.helpers import config_validation as cv

from .const import NumberConf
from .dpt import DPTInfo, get_supported_dpts


def dpt_subclass_validator(dpt_base_class: type[DPTBase]) -> Callable[[Any], str | int]:
    """Validate that value is parsable as given sensor type."""

    def dpt_value_validator(value: Any) -> str | int:
        """Validate that value is parsable as sensor type."""
        if (
            isinstance(value, (str, int))
            and dpt_base_class.parse_transcoder(value) is not None
        ):
            return value
        raise vol.Invalid(
            f"type '{value}' is not a valid DPT identifier for"
            f" {dpt_base_class.__name__}."
        )

    return dpt_value_validator


dpt_base_type_validator = dpt_subclass_validator(DPTBase)  # type: ignore[type-abstract]
numeric_type_validator = dpt_subclass_validator(DPTNumeric)  # type: ignore[type-abstract]
string_type_validator = dpt_subclass_validator(DPTString)
sensor_type_validator = vol.Any(numeric_type_validator, string_type_validator)


def ga_validator(value: Any) -> str | int:
    """Validate that value is parsable as GroupAddress or InternalGroupAddress."""
    if not isinstance(value, (str, int)):
        raise vol.Invalid(
            f"'{value}' is not a valid KNX group address: Invalid type '{type(value).__name__}'"
        )
    try:
        parse_device_group_address(value)
    except CouldNotParseAddress as exc:
        raise vol.Invalid(
            f"'{value}' is not a valid KNX group address: {exc.message}"
        ) from exc
    return value


def maybe_ga_validator(value: Any) -> str | int | None:
    """Validate a group address or None."""
    # this is a version of vol.Maybe(ga_validator) that delivers the
    # error message of ga_validator if validation fails.
    return ga_validator(value) if value is not None else None


ga_list_validator = vol.All(
    cv.ensure_list,
    [ga_validator],
    vol.IsTrue("value must be a group address or a list containing group addresses"),
)

ga_list_validator_optional = vol.Maybe(
    vol.All(
        cv.ensure_list,
        [ga_validator],
        vol.Any(vol.IsTrue(), vol.SetTo(None)),  # avoid empty lists -> None
    )
)

ia_validator = vol.Any(
    vol.All(str, str.strip, cv.matches_regex(IndividualAddress.ADDRESS_RE.pattern)),
    vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    msg=(
        "value does not match pattern for KNX individual address"
        " '<area>.<line>.<device>' (eg.'1.1.100')"
    ),
)


def ip_v4_validator(value: Any, multicast: bool | None = None) -> str:
    """Validate that value is parsable as IPv4 address.

    Optionally check if address is in a reserved multicast block or is explicitly not.
    """
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as ex:
        raise vol.Invalid(f"value '{value}' is not a valid IPv4 address: {ex}") from ex
    if multicast is not None and address.is_multicast != multicast:
        raise vol.Invalid(
            f"value '{value}' is not a valid IPv4"
            f" {'multicast' if multicast else 'unicast'} address"
        )
    return str(address)


sync_state_validator = vol.Any(
    vol.All(vol.Coerce(int), vol.Range(min=2, max=1440)),
    cv.boolean,
    cv.matches_regex(r"^(init|expire|every)( \d*)?$"),
)


def backwards_compatible_xknx_climate_enum_member(enumClass: type[Enum]) -> vol.All:
    """Transform a string to an enum member.

    Backwards compatible with member names of xknx 2.x climate DPT Enums
    due to unintentional breaking change in HA 2024.8.
    """

    def _string_transform(value: Any) -> str:
        """Upper and slugify string and substitute old member names.

        Previously this was checked against Enum values instead of names. These
        looked like `FAN_ONLY = "Fan only"`, therefore the upper & replace part.
        """
        if not isinstance(value, str):
            raise vol.Invalid("value should be a string")
        name = value.upper().replace(" ", "_")
        match name:
            case "NIGHT":
                return "ECONOMY"
            case "FROST_PROTECTION":
                return "BUILDING_PROTECTION"
            case "DRY":
                return "DEHUMIDIFICATION"
            case _:
                return name

    return vol.All(
        _string_transform,
        vol.In(enumClass.__members__),
        enumClass.__getitem__,
    )


def validate_number_attributes(
    transcoder: type[DPTNumeric], config: dict[str, Any]
) -> dict[str, Any]:
    """Validate a number entity configurations dependent on configured value type.

    Works for both, UI and YAML configuration schema since they
    share same names for all tested attributes.
    """
    min_config: float | None = config.get(NumberConf.MIN)
    max_config: float | None = config.get(NumberConf.MAX)
    step_config: float | None = config.get(NumberConf.STEP)
    _dpt_error_str = f"DPT {transcoder.dpt_number_str()} '{transcoder.value_type}'"

    # Infinity is not supported by Home Assistant frontend so user defined
    # config is required if xknx DPTNumeric subclass defines it as limit.
    if min_config is None and transcoder.value_min == -math.inf:
        raise vol.Invalid(
            f"'min' key required for {_dpt_error_str}",
            path=[NumberConf.MIN],
        )
    if min_config is not None and min_config < transcoder.value_min:
        raise vol.Invalid(
            f"'min: {min_config}' undercuts possible minimum"
            f" of {_dpt_error_str}: {transcoder.value_min}",
            path=[NumberConf.MIN],
        )
    if max_config is None and transcoder.value_max == math.inf:
        raise vol.Invalid(
            f"'max' key required for {_dpt_error_str}",
            path=[NumberConf.MAX],
        )
    if max_config is not None and max_config > transcoder.value_max:
        raise vol.Invalid(
            f"'max: {max_config}' exceeds possible maximum"
            f" of {_dpt_error_str}: {transcoder.value_max}",
            path=[NumberConf.MAX],
        )
    if step_config is not None and step_config < transcoder.resolution:
        raise vol.Invalid(
            f"'step: {step_config}' undercuts possible minimum step"
            f" of {_dpt_error_str}: {transcoder.resolution}",
            path=[NumberConf.STEP],
        )

    # Validate device class and unit of measurement compatibility
    dpt_metadata = get_supported_dpts()[transcoder.dpt_number_str()]

    device_class = config.get(
        CONF_DEVICE_CLASS,
        dpt_metadata["sensor_device_class"],
    )
    unit_of_measurement = config.get(
        CONF_UNIT_OF_MEASUREMENT,
        dpt_metadata["unit"],
    )
    if (
        device_class
        and (d_c_units := NUMBER_DEVICE_CLASS_UNITS.get(device_class)) is not None
        and unit_of_measurement not in d_c_units
    ):
        raise vol.Invalid(
            f"Unit of measurement '{unit_of_measurement}' is not valid for device class '{device_class}'. "
            f"Valid options are: {', '.join(sorted(map(str, d_c_units), key=str.casefold))}",
            path=(
                [CONF_DEVICE_CLASS]
                if CONF_DEVICE_CLASS in config
                else [CONF_UNIT_OF_MEASUREMENT]
            ),
        )

    return config


def validate_sensor_attributes(
    dpt_info: DPTInfo, config: dict[str, Any]
) -> dict[str, Any]:
    """Validate that state_class is compatible with device_class and unit_of_measurement.

    Works for both, UI and YAML configuration schema since they
    share same names for all tested attributes.
    """
    state_class = config.get(
        CONF_SENSOR_STATE_CLASS,
        dpt_info["sensor_state_class"],
    )
    device_class = config.get(
        CONF_DEVICE_CLASS,
        dpt_info["sensor_device_class"],
    )
    unit_of_measurement = config.get(
        CONF_UNIT_OF_MEASUREMENT,
        dpt_info["unit"],
    )
    if (
        state_class
        and device_class
        and (state_classes := DEVICE_CLASS_STATE_CLASSES.get(device_class)) is not None
        and state_class not in state_classes
    ):
        raise vol.Invalid(
            f"State class '{state_class}' is not valid for device class '{device_class}'. "
            f"Valid options are: {', '.join(sorted(map(str, state_classes), key=str.casefold))}",
            path=[CONF_SENSOR_STATE_CLASS],
        )
    if (
        device_class
        and (d_c_units := DEVICE_CLASS_UNITS.get(device_class)) is not None
        and unit_of_measurement not in d_c_units
    ):
        raise vol.Invalid(
            f"Unit of measurement '{unit_of_measurement}' is not valid for device class '{device_class}'. "
            f"Valid options are: {', '.join(sorted(map(str, d_c_units), key=str.casefold))}",
            path=(
                [CONF_DEVICE_CLASS]
                if CONF_DEVICE_CLASS in config
                else [CONF_UNIT_OF_MEASUREMENT]
            ),
        )
    if (
        state_class
        and (s_c_units := STATE_CLASS_UNITS.get(state_class)) is not None
        and unit_of_measurement not in s_c_units
    ):
        raise vol.Invalid(
            f"Unit of measurement '{unit_of_measurement}' is not valid for state class '{state_class}'. "
            f"Valid options are: {', '.join(sorted(map(str, s_c_units), key=str.casefold))}",
            path=(
                [CONF_SENSOR_STATE_CLASS]
                if CONF_SENSOR_STATE_CLASS in config
                else [CONF_UNIT_OF_MEASUREMENT]
            ),
        )
    return config
