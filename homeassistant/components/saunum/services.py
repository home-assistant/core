"""Define services for the Saunum integration."""

from __future__ import annotations

from typing import cast

from pysaunum import (
    MAX_DURATION,
    MAX_FAN_DURATION,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    SaunumException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector

from .const import DOMAIN
from .coordinator import LeilSaunaCoordinator

ATTR_DURATION = "duration"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_FAN_DURATION = "fan_duration"
CONF_CONFIG_ENTRY_ID = "config_entry_id"

SERVICE_START_SESSION = "start_session"

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_START_SESSION_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Optional(ATTR_DURATION, default=120): vol.All(
                cv.positive_int, vol.Range(min=1, max=MAX_DURATION)
            ),
            vol.Optional(ATTR_TARGET_TEMPERATURE, default=80): vol.All(
                cv.positive_int, vol.Range(min=MIN_TEMPERATURE, max=MAX_TEMPERATURE)
            ),
            vol.Optional(ATTR_FAN_DURATION, default=10): vol.All(
                cv.positive_int, vol.Range(min=1, max=MAX_FAN_DURATION)
            ),
        }
    ),
)


def _get_coordinator_from_service_data(
    call: ServiceCall,
) -> LeilSaunaCoordinator:
    """Return coordinator for entry id."""
    config_entry_id: str = call.data[CONF_CONFIG_ENTRY_ID]
    if not (entry := call.hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(LeilSaunaCoordinator, entry.runtime_data)


async def _async_start_session(call: ServiceCall) -> None:
    """Start a sauna session with custom parameters."""
    coordinator = _get_coordinator_from_service_data(call)

    duration: int = call.data[ATTR_DURATION]
    target_temperature: int = call.data[ATTR_TARGET_TEMPERATURE]
    fan_duration: int = call.data[ATTR_FAN_DURATION]

    # Check if door is open
    if coordinator.data.door_open:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="door_open",
        )

    try:
        # Set all parameters before starting the session
        await coordinator.client.async_set_sauna_duration(duration)
        await coordinator.client.async_set_target_temperature(target_temperature)
        await coordinator.client.async_set_fan_duration(fan_duration)
        await coordinator.client.async_start_session()
    except SaunumException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="start_session_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Saunum integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SESSION,
        _async_start_session,
        schema=SERVICE_START_SESSION_SCHEMA,
    )
