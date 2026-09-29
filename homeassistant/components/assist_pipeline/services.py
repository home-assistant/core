"""Services for the Assist pipeline integration."""

import time

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service

from .const import ATTR_DAYS, DOMAIN, SERVICE_CLEAR_DEBUG_RECORDINGS
from .debug_recording import (
    async_check_debug_recordings,
    async_get_debug_recording_dir,
    delete_debug_recordings,
)


async def async_service_clear_debug_recordings(call: ServiceCall) -> None:
    """Delete the debug recordings, or only those older than the given days."""
    hass = call.hass
    if (recording_dir := async_get_debug_recording_dir(hass)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="debug_recording_dir_not_configured",
        )
    older_than = None
    if (days := call.data.get(ATTR_DAYS)) is not None:
        older_than = time.time() - days * 86400
    try:
        await hass.async_add_executor_job(
            delete_debug_recordings, recording_dir, older_than
        )
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="delete_debug_recordings_failed",
        ) from err
    finally:
        # Also after a failure, as some recordings may be deleted already.
        await async_check_debug_recordings(hass, recording_dir)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Assist pipeline services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_DEBUG_RECORDINGS,
        async_service_clear_debug_recordings,
        schema=probatio.Schema(
            {
                probatio.Optional(ATTR_DAYS): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=1, max=3650)
                )
            }
        ),
    )
