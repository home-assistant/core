"""Custom services for the Daikin integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_ZONE_TEMPERATURE = "set_zone_temperature"

@dataclass(slots=True)
class SetZoneTemperatureData:
    """Data for set_zone_temperature service."""

    zone_id: int
    temperature: float
    entry_id: str | None = None

SERVICE_SET_ZONE_TEMPERATURE_SCHEMA = vol.Schema(
    {
        vol.Required("zone_id"): vol.Coerce(int),
        vol.Required("temperature"): vol.Coerce(float),
        vol.Optional("entry_id"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom Daikin services."""
    if hasattr(hass.services, "_daikin_services_registered"):
        return
    setattr(hass.services, "_daikin_services_registered", True)

    async def async_handle_set_zone_temperature(call: ServiceCall) -> None:
        """Handle the set_zone_temperature service call."""
        data = SetZoneTemperatureData(
            zone_id=call.data["zone_id"],
            temperature=call.data["temperature"],
            entry_id=call.data.get("entry_id"),
        )
        _LOGGER.debug(
            "Received call to set zone_id=%s to temperature=%s", data.zone_id, data.temperature
        )
        coordinators: dict[str, Any]
        if data.entry_id:
            coordinators = {data.entry_id: hass.data.get(DOMAIN, {}).get(data.entry_id)}
        else:
            coordinators = hass.data.get(DOMAIN, {})

        async def set_temp(entry_id: str, coordinator: Any) -> None:
            if coordinator is None:
                _LOGGER.warning("No coordinator found for entry %s", entry_id)
                return
            device = getattr(coordinator, "device", None)
            if not device:
                _LOGGER.warning("No device found in coordinator for entry %s", entry_id)
                return
            match device:
                case _ if hasattr(device, "target_temperature"):
                    target_temp = device.target_temperature
                case _:
                    target_temp = 22
                    _LOGGER.debug("Using default target temperature of 22 for range check")
            min_temp, max_temp = target_temp - 2, target_temp + 2
            if not (min_temp <= data.temperature <= max_temp):
                raise HomeAssistantError(
                    f"Value {data.temperature}°C out of range ({min_temp}°C - {max_temp}°C)"
                )
            retries = 3
            for attempt in range(retries):
                try:
                    _LOGGER.debug(
                        "Attempting to set zone %s to %s°C on device %s (attempt %s)",
                        data.zone_id,
                        data.temperature,
                        getattr(device, "mac", "unknown"),
                        attempt + 1,
                    )
                    await device.set_zone(data.zone_id, "lztemp_h", str(round(data.temperature)))
                    _LOGGER.debug(
                        "Successfully set temperature for zone %s to %s°C on device %s",
                        data.zone_id,
                        data.temperature,
                        getattr(device, "mac", "unknown"),
                    )
                    break
                except (IndexError, KeyError, AttributeError) as err:
                    _LOGGER.error(
                        "Attempt %s: Failed to set zone temperature on device %s: %s",
                        attempt + 1,
                        getattr(device, "mac", "unknown"),
                        err,
                    )
                    if attempt == retries - 1:
                        raise HomeAssistantError(
                            f"Failed to set zone temperature after {retries} attempts: {err}"
                        ) from err
                    await asyncio.sleep(1)
        await asyncio.gather(*(set_temp(entry_id, coordinator) for entry_id, coordinator in coordinators.items()))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ZONE_TEMPERATURE,
        async_handle_set_zone_temperature,
        schema=SERVICE_SET_ZONE_TEMPERATURE_SCHEMA,
    )
    _LOGGER.info("Daikin custom services registered")

async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Daikin custom services. Called if the integration is fully unloaded (e.g., last config entry removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZONE_TEMPERATURE)
    if hasattr(hass.services, "_daikin_services_registered"):
        delattr(hass.services, "_daikin_services_registered")
    _LOGGER.info("Daikin custom services unregistered")
