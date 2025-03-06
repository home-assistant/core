"""Custom services for the Daikin integration."""

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Name of the custom service, e.g. "daikin.set_zone_temperature"
SERVICE_SET_ZONE_TEMPERATURE = "set_zone_temperature"

# Define the schema of the service arguments
SERVICE_SET_ZONE_TEMPERATURE_SCHEMA = vol.Schema(
    {
        vol.Required("zone_id"): vol.Coerce(int),       # Which zone to set
        vol.Required("temperature"): vol.Coerce(float), # Desired temperature
        vol.Optional("entry_id"): cv.string             # Daikin device to target
    }
)

async def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom Daikin services. Called typically from __init__.py or async_setup_entry once the integration is initialized."""

    async def async_handle_set_zone_temperature(call: ServiceCall) -> None:
        """Handle the set_zone_temperature service call."""
        zone_id = call.data["zone_id"]
        temperature = call.data["temperature"]

        _LOGGER.debug(
            "Received call to set zone_id=%s to temperature=%s",
            zone_id,
            temperature,
        )

        # If an entry_id is provided, only target that coordinator.
        entry_filter = call.data.get("entry_id")
        if entry_filter:
            coordinators = {entry_filter: hass.data.get(DOMAIN, {}).get(entry_filter)}
        else:
            coordinators = hass.data.get(DOMAIN, {})

        for entry_id, coordinator in coordinators.items():
            if coordinator is None:
                _LOGGER.warning("No coordinator found for entry %s", entry_id)
                continue

            device = getattr(coordinator, "device", None)
            if not device:
                _LOGGER.warning("No device found in coordinator for entry %s", entry_id)
                continue

# Retrieve the device's target_temperature (default 22 if missing)
            try:
                target_temp = device.target_temperature
            except AttributeError:
                target_temp = 22
                _LOGGER.debug("Using default target temperature of 22 for range check.")

# Define allowed range: [target_temp - 2, target_temp + 2]
            min_temp = target_temp - 2
            max_temp = target_temp + 2

# Enforce the range limit
            if not (min_temp <= temperature <= max_temp):
                raise HomeAssistantError(
                    f"Value {temperature}°C out of range ({min_temp}°C - {max_temp}°C)."
                )

# Set zone temp with retry logic
            retries = 3
            for attempt in range(retries):
                try:
                    _LOGGER.debug(
                        "Attempting to set zone %s to %s°C on device %s (attempt %s)",
                        zone_id,
                        temperature,
                        device.mac,
                        attempt + 1,
                    )
                    await device.set_zone(zone_id, "lztemp_h", str(round(temperature)))
                    break
                except (IndexError, KeyError, AttributeError) as err:
                    _LOGGER.error(
                        "Attempt %s: Failed to set zone temperature on device %s: %s",
                        attempt + 1,
                        device.mac,
                        err,
                    )
                    if attempt == retries - 1:
                        _LOGGER.error(
                            "Failed to set zone temperature after %s attempts: %s",
                            retries,
                            err,
                        )
                    else:
                        await asyncio.sleep(1)  # small delay before next attempt

    # Register the service with Home Assistant
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ZONE_TEMPERATURE,
        async_handle_set_zone_temperature,
        schema=SERVICE_SET_ZONE_TEMPERATURE_SCHEMA,
    )

    _LOGGER.info("Daikin custom services registered.")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Daikin custom services. Called if the integration is fully unloaded (e.g., last config entry removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZONE_TEMPERATURE)
    _LOGGER.info("Daikin custom services unregistered.")
