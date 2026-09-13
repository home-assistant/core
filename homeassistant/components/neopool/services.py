"""Services for the NeoPool integration."""

import logging
from typing import Any

from neopool_modbus.decoders import (
    combine_u32,
    decode_device_time,
    get_timer_interval,
    hhmm_to_seconds,
)
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import (
    DEVICE_TIME_REGISTER,
    MAX_REGISTERS_PER_READ,
    TIMER_BLOCKS,
)
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import NeoPoolCoordinator
from .helpers import parse_register_int, prepare_device_time

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TIMER = "set_timer"
SERVICE_WRITE_REGISTER = "write_register"
SERVICE_READ_REGISTER = "read_register"
SERVICE_GET_DEVICE_TIME = "get_device_time"
SERVICE_SET_DEVICE_TIME = "set_device_time"

ATTR_TIMER = "timer"
ATTR_START = "start"
ATTR_STOP = "stop"
ATTR_PERIOD = "period"
ATTR_ENABLE = "enable"
ATTR_ADDRESS = "address"
ATTR_VALUE = "value"
ATTR_APPLY = "apply"
ATTR_COUNT = "count"

SERVICE_SET_TIMER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_TIMER): cv.string,
        vol.Optional(ATTR_START): cv.string,
        vol.Optional(ATTR_STOP): cv.string,
        vol.Optional(ATTR_PERIOD): vol.All(int, vol.Range(min=1, max=604800)),
        vol.Optional(ATTR_ENABLE): vol.All(int, vol.Range(min=0, max=4)),
    }
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Required(ATTR_VALUE): cv.string,
        vol.Optional(ATTR_APPLY, default=True): cv.boolean,
    }
)

SERVICE_READ_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Optional(ATTR_COUNT, default=1): vol.All(
            int, vol.Range(min=1, max=MAX_REGISTERS_PER_READ)
        ),
    }
)

SERVICE_DEVICE_TIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)


async def _get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> NeoPoolCoordinator:
    """Resolve the coordinator for a service call.

    If a target `device_id` is provided in the service data, resolve it via
    the config-entry extraction helper to a loaded NeoPool config entry. If
    omitted, fall back to the single loaded entry; error if none or more than
    one exist. The resolved entry must have a populated `runtime_data` (the
    coordinator). Raises ServiceValidationError if any of those conditions is
    not met.
    """
    loaded = hass.config_entries.async_loaded_entries(DOMAIN)
    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id:
        target_ids = await async_extract_config_entry_ids(call)
        entry = next((e for e in loaded if e.entry_id in target_ids), None)
        if entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"device_id": device_id},
            )
    elif not loaded:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_loaded_entry",
        )
    elif len(loaded) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_entries_no_device",
        )
    else:
        entry = loaded[0]
    coordinator: NeoPoolCoordinator | None = entry.runtime_data
    if coordinator is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_coordinator",
            translation_placeholders={"entry_id": entry.entry_id},
        )
    return coordinator


async def _async_set_timer(call: ServiceCall) -> None:
    """Set a timer on the pool controller."""
    timer_name = call.data[ATTR_TIMER]
    if timer_name not in TIMER_BLOCKS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_timer",
            translation_placeholders={
                "timer_name": timer_name,
                "valid_timers": ", ".join(sorted(TIMER_BLOCKS)),
            },
        )

    coordinator = await _get_coordinator(call.hass, call)
    start = call.data.get(ATTR_START)
    stop = call.data.get(ATTR_STOP)
    period = call.data.get(ATTR_PERIOD)
    enable = call.data.get(ATTR_ENABLE)

    try:
        start_sec = hhmm_to_seconds(start) if start is not None else None
        stop_sec = hhmm_to_seconds(stop) if stop is not None else None
        interval: int | None = None
        if start_sec is not None and stop_sec is not None:
            interval = get_timer_interval(start_sec, stop_sec)
    except (TypeError, ValueError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_timer_time",
            translation_placeholders={"start": str(start), "stop": str(stop)},
        ) from err

    timer_data: dict[str, Any] = {}
    if start_sec is not None:
        timer_data["on"] = start_sec
    if interval is not None:
        timer_data["interval"] = interval
    if period is not None:
        timer_data["period"] = period
    if enable is not None:
        timer_data["enable"] = enable

    _LOGGER.debug("Setting timer %s with data: %s", timer_name, timer_data)
    try:
        await coordinator.client.write_timer(timer_name, timer_data)
    except (NeoPoolError, OSError) as err:
        _LOGGER.error(
            "Failed to set timer %s: %s (%s)",
            timer_name,
            err,
            type(err).__name__,
        )
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="timer_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    coordinator.request_refresh_with_followup()


async def _async_write_register(call: ServiceCall) -> None:
    """Write a value to a Modbus holding register."""
    address = parse_register_int(call.data[ATTR_ADDRESS], "address")
    value = parse_register_int(call.data[ATTR_VALUE], "value")
    apply = call.data[ATTR_APPLY]
    coordinator = await _get_coordinator(call.hass, call)

    try:
        result = await coordinator.client.async_write_register(
            address, value, apply=apply
        )
    except (NeoPoolError, OSError) as err:
        _LOGGER.error(
            "Failed to write register 0x%04X: %s (%s)",
            address,
            err,
            type(err).__name__,
        )
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="register_write_failed",
            translation_placeholders={
                "address": f"0x{address:04X}",
                "error": str(err),
            },
        ) from err

    if result is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
            translation_placeholders={"address": f"0x{address:04X}"},
        )

    confirmed = result.get("confirmed")
    _LOGGER.debug(
        "Service write_register: 0x%04X = %s (confirmed: %s, apply: %s)",
        address,
        result.get("value"),
        confirmed,
        apply,
    )
    if confirmed != value:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="write_verification_failed",
            translation_placeholders={
                "address": f"0x{address:04X}",
                "value": str(value),
                "confirmed": str(confirmed),
            },
        )
    coordinator.request_refresh_with_followup()


async def _async_read_register(call: ServiceCall) -> ServiceResponse:
    """Read one or more Modbus registers and return the raw u16 values."""
    address = parse_register_int(call.data[ATTR_ADDRESS], "address")
    count = call.data[ATTR_COUNT]
    coordinator = await _get_coordinator(call.hass, call)

    try:
        registers = await coordinator.client.async_read_register(address, count)
    except (NeoPoolError, OSError, ValueError) as err:
        _LOGGER.error(
            "Failed to read register 0x%04X (count=%d): %s (%s)",
            address,
            count,
            err,
            type(err).__name__,
        )
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="register_read_failed",
            translation_placeholders={
                "address": f"0x{address:04X}",
                "error": str(err),
            },
        ) from err

    if len(registers) != count:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="register_read_failed",
            translation_placeholders={
                "address": f"0x{address:04X}",
                "error": f"short read ({len(registers)}/{count} words)",
            },
        )

    _LOGGER.debug(
        "Service read_register: 0x%04X (count=%d) -> %s",
        address,
        count,
        registers,
    )
    response: dict[str, Any] = {
        "address": f"0x{address:04X}",
        "count": count,
        "values": registers,
    }
    if count == 1:
        response["value"] = registers[0]
    return response


async def _async_get_device_time(call: ServiceCall) -> ServiceResponse:
    """Return the device RTC wall-clock and its drift from Home Assistant.

    Reads only the two clock registers directly from the controller at call
    time, so the drift is accurate regardless of the polling interval and
    without pulling the full register set.
    """
    coordinator = await _get_coordinator(call.hass, call)

    try:
        regs = await coordinator.client.async_read_register(DEVICE_TIME_REGISTER, 2)
    except (NeoPoolError, OSError, ValueError) as err:
        _LOGGER.error("Failed to read device time: %s (%s)", err, type(err).__name__)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_time_read_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if len(regs) < 2:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_time_read_failed",
            translation_placeholders={"error": f"short read ({len(regs)} words)"},
        )

    tz = dt_util.get_time_zone(call.hass.config.time_zone) or dt_util.UTC
    device_dt = decode_device_time(combine_u32(regs[0], regs[1]), tz)
    if device_dt is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_time_read_failed",
            translation_placeholders={"error": "invalid clock value"},
        )

    now = dt_util.utcnow().replace(microsecond=0)
    drift = round((device_dt - now).total_seconds())
    return {
        "device_time": device_dt.isoformat(),
        "ha_time": now.isoformat(),
        "drift_seconds": drift,
    }


async def _async_set_device_time(call: ServiceCall) -> None:
    """Write the current Home Assistant time to the device RTC."""
    coordinator = await _get_coordinator(call.hass, call)
    timestamp = prepare_device_time(call.hass)

    try:
        result = await coordinator.client.async_sync_device_time(timestamp)
    except (NeoPoolError, OSError) as err:
        _LOGGER.error("Failed to set device time: %s (%s)", err, type(err).__name__)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_time_write_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if result is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_time_write_failed",
            translation_placeholders={"error": "no response"},
        )

    _LOGGER.debug("Service set_device_time: wrote %s to device RTC", timestamp)
    coordinator.request_refresh_with_followup()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the NeoPool services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_TIMER,
        _async_set_timer,
        schema=SERVICE_SET_TIMER_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        _async_write_register,
        schema=SERVICE_WRITE_REGISTER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_REGISTER,
        _async_read_register,
        schema=SERVICE_READ_REGISTER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DEVICE_TIME,
        _async_get_device_time,
        schema=SERVICE_DEVICE_TIME_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_DEVICE_TIME,
        _async_set_device_time,
        schema=SERVICE_DEVICE_TIME_SCHEMA,
    )
