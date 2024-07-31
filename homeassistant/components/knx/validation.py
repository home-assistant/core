"""Validation helpers for KNX config schemas."""

from collections.abc import Callable
import ipaddress
from typing import Any

import voluptuous as vol
from xknx.dpt import DPTBase, DPTNumeric, DPTString
from xknx.exceptions import CouldNotParseAddress
from xknx.telegram.address import IndividualAddress, parse_device_group_address

import homeassistant.helpers.config_validation as cv


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


numeric_type_validator = dpt_subclass_validator(DPTNumeric)  # type: ignore[type-abstract]
sensor_type_validator = dpt_subclass_validator(DPTBase)  # type: ignore[type-abstract]
string_type_validator = dpt_subclass_validator(DPTString)


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
