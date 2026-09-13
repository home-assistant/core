"""Helper functions for the NeoPool integration."""

import datetime

from neopool_modbus.decoders import (
    encode_device_time,
    parse_register_int as _lib_parse_register_int,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.util.dt as dt_util

from .const import DOMAIN


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
    return encode_device_time(dt_util.now(tz))


def parse_register_int(raw: int | str, name: str) -> int:
    """Parse a Modbus register value, raising a translated ServiceValidationError."""
    try:
        return _lib_parse_register_int(raw)
    except ValueError as err:
        msg = str(err)
        if msg.startswith("register value out of range"):
            key = "register_out_of_range"
        elif msg.startswith("register value must not be a float"):
            key = "invalid_register_float"
        else:
            # bool / unparsable string / unsupported type all collapse to
            # the generic "invalid type" translation.
            key = "invalid_register_type"
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders={"name": name, "value": str(raw)},
        ) from err
