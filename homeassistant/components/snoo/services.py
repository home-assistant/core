"""Services for the Snoo integration."""

from __future__ import annotations

import logging

from python_snoo.containers import DiaperActivity, DiaperTypes
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DEVICE_ID_BABY,
    ATTR_DIAPER_CHANGE_TYPES,
    ATTR_NOTE,
    ATTR_START_TIME,
    DOMAIN,
    SERVICE_LOG_DIAPER_CHANGE,
)
from .coordinator import SnooBabyCoordinator, SnooConfigEntry, SnooCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schema for log_diaper_change
LOG_DIAPER_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID_BABY): cv.string,
        vol.Required(ATTR_DIAPER_CHANGE_TYPES): vol.All(
            cv.ensure_list,
            [vol.In(["wet", "dirty"])],
        ),
        vol.Optional(ATTR_NOTE): cv.string,
        vol.Optional(ATTR_START_TIME): cv.datetime,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Snoo integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_DIAPER_CHANGE,
        _async_log_diaper_change,
        schema=LOG_DIAPER_CHANGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_log_diaper_change(call: ServiceCall) -> ServiceResponse:
    """Log a diaper change for the baby."""

    def _raise_no_config_error() -> None:
        """Raise error when no Snoo configuration is found."""
        raise HomeAssistantError("No Snoo configuration found")

    def _raise_device_not_found_error(device_id: str) -> None:
        """Raise error when device is not found."""
        raise HomeAssistantError(f"Device '{device_id}' not found")

    def _raise_invalid_device_error(device_id: str) -> None:
        """Raise error when device is invalid."""
        raise HomeAssistantError(
            f"Device '{device_id}' is not a valid baby device because it has no serial number."
        )

    def _raise_baby_not_found_error(baby_id: str) -> None:
        """Raise error when baby ID is not found."""
        raise HomeAssistantError(
            f"Baby {baby_id} is not an available baby from the Snoo integration."
        )

    config_entries: list[SnooConfigEntry] = call.hass.config_entries.async_entries(
        DOMAIN, include_ignore=False, include_disabled=False
    )

    if not config_entries:
        _raise_no_config_error()

    baby_device_id = call.data[ATTR_DEVICE_ID_BABY]

    device_registry = dr.async_get(call.hass)
    device: dr.DeviceEntry | None = device_registry.async_get(baby_device_id)
    if not device:
        _raise_device_not_found_error(baby_device_id)
    assert device is not None

    baby_id: str | None = device.serial_number
    if not baby_id:
        _raise_invalid_device_error(baby_device_id)
    assert baby_id is not None

    baby_coordinator: SnooBabyCoordinator | None = None

    for entry in config_entries:
        coordinators: dict[str, SnooCoordinator] = entry.runtime_data
        if not coordinators:
            _LOGGER.warning("No coordinators found for config entry %s", entry.entry_id)
            continue

        for coordinator in coordinators.values():
            for bid, baby_coord in coordinator.baby_coordinators.items():
                if bid == baby_id:
                    baby_coordinator = baby_coord
                    break

    if baby_coordinator is None:
        _raise_baby_not_found_error(baby_id)
    assert baby_coordinator is not None

    start_time = call.data.get(ATTR_START_TIME)
    if start_time is not None and start_time.tzinfo is None:
        # Assume local time is coming in with a custom timestamp
        start_time = dt_util.as_local(start_time)

    result: DiaperActivity = await baby_coordinator.baby.log_diaper_change(
        [DiaperTypes[dt.upper()] for dt in call.data[ATTR_DIAPER_CHANGE_TYPES]],
        note=call.data.get(ATTR_NOTE),
        start_time=start_time,
    )

    _LOGGER.info(
        "Diaper change logged for baby %s: %s",
        baby_id,
        call.data[ATTR_DIAPER_CHANGE_TYPES],
    )

    return result.to_dict()
