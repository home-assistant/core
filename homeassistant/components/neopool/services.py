"""Services for the NeoPool integration."""

import logging

from neopool_modbus.decoders import combine_u32, decode_device_time
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import DEVICE_TIME_REGISTER
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import NeoPoolCoordinator
from .helpers import prepare_device_time

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_DEVICE_TIME = "get_device_time"
SERVICE_SET_DEVICE_TIME = "set_device_time"

SERVICE_DEVICE_TIME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_DEVICE_ID): cv.string,
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
    if device_id is not None:
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_time_read_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if len(regs) < 2:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_time_read_failed",
            translation_placeholders={"error": f"short read ({len(regs)} words)"},
        )

    tz = dt_util.get_time_zone(call.hass.config.time_zone) or dt_util.UTC
    device_dt = decode_device_time(combine_u32(regs[0], regs[1]), tz)
    if device_dt is None:
        raise HomeAssistantError(
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_time_write_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if result is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_time_write_failed",
            translation_placeholders={"error": "no response"},
        )

    _LOGGER.debug("Service set_device_time: wrote %s to device RTC", timestamp)
    coordinator.request_refresh_with_followup()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the NeoPool services."""
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
