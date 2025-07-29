"""Services for the Snoo integration."""

from __future__ import annotations

import logging

from python_snoo.baby import Baby
from python_snoo.containers import DiaperTypes
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Service schema for log_diaper_change
LOG_DIAPER_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required("baby_id"): cv.string,
        vol.Required("diaper_types"): vol.All(
            cv.ensure_list,
            [vol.In([k.title() for k in DiaperTypes.__members__])],
        ),
        vol.Optional("note"): cv.string,
        vol.Optional("start_time"): cv.datetime,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Snoo integration."""
    hass.services.async_register(
        DOMAIN,
        "log_diaper_change",
        _async_log_diaper_change,
        schema=LOG_DIAPER_CHANGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_log_diaper_change(call: ServiceCall) -> ServiceResponse:
    """Log a diaper change for the baby."""

    def _raise_no_config_error() -> None:
        """Raise error when no Snoo configuration is found."""
        raise HomeAssistantError("No Snoo configuration found")

    def _raise_baby_not_found_error(baby_id: str, available_babies: str) -> None:
        """Raise error when baby ID is not found."""
        raise HomeAssistantError(
            f"Baby ID '{baby_id}' not found. Available baby IDs: {available_babies}"
        )

    config_entries = call.hass.config_entries.async_entries(DOMAIN)
    if not config_entries:
        _raise_no_config_error()

    baby_id = call.data["baby_id"]
    snoo = None
    all_baby_ids = []

    for entry in config_entries:
        coordinators = entry.runtime_data
        if not coordinators:
            _LOGGER.warning("No coordinators found for config entry %s", entry.entry_id)
            continue

        for coordinator in coordinators.values():
            device = coordinator.device
            if device.babyIds:
                all_baby_ids.extend(device.babyIds)
                if baby_id in device.babyIds:
                    snoo = coordinator.snoo
                    break
        if snoo:
            break

    if not snoo:
        available_babies = ", ".join(all_baby_ids)
        _raise_baby_not_found_error(baby_id, available_babies)

    start_time = call.data.get("start_time")
    if start_time is not None and start_time.tzinfo is None:
        # Assume local time is coming in with a custom timestamp
        start_time = dt_util.as_local(start_time)

    baby = Baby(baby_id, snoo)
    result = await baby.log_diaper_change(
        [DiaperTypes[dt.upper()] for dt in call.data["diaper_types"]],
        note=call.data.get("note"),
        start_time=start_time,
    )

    _LOGGER.info(
        "Diaper change logged for baby %s: %s", baby_id, call.data["diaper_types"]
    )

    return result.to_dict()
