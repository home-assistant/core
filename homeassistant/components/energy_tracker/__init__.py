"""Initialization for the Energy Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .api import EnergyTrackerApi
from .const import CONF_API_TOKEN, DOMAIN, SERVICE_SEND_METER_READING

type EnergyTrackerConfigEntry = ConfigEntry[str]

LOGGER = logging.getLogger(__name__)

SERVICE_SEND_METER_READING_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("source_entity_id"): cv.entity_id,
        vol.Required("entry_id"): cv.string,
        vol.Optional("allow_rounding", default=True): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Energy Tracker integration (YAML-based, legacy)."""
    LOGGER.debug("async_setup called for Energy Tracker (YAML not supported)")
    return True


def _select_token_for_service(hass: HomeAssistant, call: ServiceCall) -> str | None:
    """Select the API token for a service call.

    Retrieves the API token for the Energy Tracker integration based on the
    config entry ID provided in the service call data.

    Args:
        hass: The Home Assistant instance.
        call: The service call containing the 'entry_id'.

    Returns:
        The API token as a string if found, otherwise None.
    """
    entry_id: str | None = call.data.get("entry_id")
    if not entry_id:
        LOGGER.debug("No entry ID provided")
        return None

    entry: EnergyTrackerConfigEntry | None = hass.config_entries.async_get_entry(
        entry_id
    )
    if not entry:
        LOGGER.debug("Integration with ID %s was deleted", entry_id)
        return None

    token = entry.runtime_data
    if not token:
        LOGGER.error("API token not found for entry ID %s", entry_id)
        return None

    return token


async def async_handle_send_meter_reading(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle the send_meter_reading service.

    Reads the current value from a Home Assistant entity and sends it
    as a meter reading to the Energy Tracker backend.

    Raises:
        HomeAssistantError: If the meter reading could not be sent.
    """
    device_id: str = call.data["device_id"].strip()
    source_entity_id: str = call.data["source_entity_id"]
    allow_rounding: bool = call.data.get("allow_rounding", True)

    state_obj: State | None = hass.states.get(source_entity_id)
    if state_obj is None:
        LOGGER.error("Source entity %s not found", source_entity_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": source_entity_id},
        )

    raw_state = state_obj.state
    if raw_state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        LOGGER.warning("Source entity %s is %s", source_entity_id, raw_state)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_unavailable",
            translation_placeholders={
                "entity_id": source_entity_id,
                "state": raw_state,
            },
        )

    try:
        value = float(raw_state)
    except (TypeError, ValueError) as err:
        LOGGER.error(
            "Could not convert state '%s' of %s to number", raw_state, source_entity_id
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_number",
            translation_placeholders={
                "entity_id": source_entity_id,
                "state": raw_state,
            },
        ) from err

    if state_obj.last_updated is None:
        LOGGER.error("Source entity %s has no last_updated timestamp", source_entity_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="missing_timestamp",
            translation_placeholders={"entity_id": source_entity_id},
        )
    timestamp = state_obj.last_updated

    token = _select_token_for_service(hass, call)
    if not token:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_api_token",
        )

    api = EnergyTrackerApi(hass=hass, token=token)

    await api.send_meter_reading(
        source_entity_id=source_entity_id,
        device_id=device_id,
        value=value,
        timestamp=timestamp,
        allow_rounding=allow_rounding,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergyTrackerConfigEntry
) -> bool:
    """Set up the Energy Tracker integration from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The configuration entry to set up.

    Returns:
        True if setup was successful, False otherwise.
    """
    LOGGER.debug("Setting up config entry %s", entry.entry_id)

    entry.runtime_data = entry.data[CONF_API_TOKEN]

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING):

        async def _handle_send_meter_reading(call: ServiceCall) -> None:
            await async_handle_send_meter_reading(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_METER_READING,
            _handle_send_meter_reading,
            schema=SERVICE_SEND_METER_READING_SCHEMA,
        )
        LOGGER.debug("Registered service %s/%s", DOMAIN, SERVICE_SEND_METER_READING)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergyTrackerConfigEntry
) -> bool:
    """Unload a config entry for the Energy Tracker integration.

    Unregisters the service if this was the last loaded config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry to unload.

    Returns:
        True if the unload was successful.
    """
    LOGGER.debug("Unloading config entry %s", entry.entry_id)

    # Check if there are other loaded entries for this domain
    loaded_entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id and e.state.recoverable
    ]

    if not loaded_entries:
        if hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING):
            hass.services.async_remove(DOMAIN, SERVICE_SEND_METER_READING)
            LOGGER.debug(
                "Removed service %s.%s after last config entry was unloaded",
                DOMAIN,
                SERVICE_SEND_METER_READING,
            )

    return True
