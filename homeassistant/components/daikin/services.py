"""Custom services for the Daikin integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any
from urllib.parse import quote
from weakref import WeakKeyDictionary

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

# Configure logging
_LOGGER = logging.getLogger(__name__)

SERVICE_SET_ZONE_TEMPERATURE = "set_zone_temperature"

# Track service registration per hass instance
_services_registered: WeakKeyDictionary[HomeAssistant, bool] = WeakKeyDictionary()


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
    if _services_registered.get(hass):
        return
    _services_registered[hass] = True

    async def async_handle_set_zone_temperature(call: ServiceCall) -> None:
        """Handle the set_zone_temperature service call."""
        data = SetZoneTemperatureData(
            zone_id=call.data["zone_id"],
            temperature=call.data["temperature"],
            entry_id=call.data.get("entry_id"),
        )
        # Find coordinators
        daikin_data = hass.data.get(DOMAIN, {})
        if data.entry_id:
            coordinators = {data.entry_id: daikin_data.get(data.entry_id)}
        elif daikin_data:
            first_entry_id = next(iter(daikin_data))
            coordinators = {first_entry_id: daikin_data[first_entry_id]}
        else:
            coordinators = {}
        if not coordinators:
            _LOGGER.error(
                "No Daikin coordinators found in hass.data[DOMAIN]. Service cannot proceed"
            )
            return

        async def set_temp(entry_id: str, coordinator: Any) -> None:
            if coordinator is None:
                _LOGGER.warning("No coordinator found for entry %s", entry_id)
                return
            device = getattr(coordinator, "device", None)
            if not device:
                _LOGGER.warning("No device found in coordinator for entry %s", entry_id)
                return
            zones = getattr(device, "zones", None)
            if not zones:
                _LOGGER.warning("Device does not support zones")
                return
            try:
                zone = zones[data.zone_id]
                if zone[0] == "-" or zone[2] == 0:
                    raise HomeAssistantError(
                        f"Zone {data.zone_id} is not active. "
                        "Please enable the zone in your Daikin device settings first."
                    )
            except IndexError as err:
                raise HomeAssistantError(
                    f"Zone {data.zone_id} does not exist. "
                    f"Available zones are 0-{len(zones) - 1}."
                ) from err
            try:
                target_temp = device.target_temperature
            except AttributeError:
                target_temp = 22
            min_temp, max_temp = target_temp - 2, target_temp + 2
            if not (min_temp <= data.temperature <= max_temp):
                raise HomeAssistantError(
                    f"Temperature {data.temperature}°C is outside the supported range. "
                    f"The zone temperature must be within ±2°C of the main system's target temperature "
                    f"({min_temp}°C - {max_temp}°C)."
                )
            retries = 3
            for attempt in range(retries):
                try:
                    await device.set_zone(data.zone_id, "zone_onoff", "1")
                    # ruff: noqa: SLF001
                    current_state = await device._get_resource(
                        "aircon/get_zone_setting"
                    )
                    if not current_state:
                        raise HomeAssistantError(
                            "Failed to get zone settings. This device may not support zone temperature control."
                        )
                    device.values.update(current_state)
                    current_heating = device.represent("lztemp_h")[1]
                    current_cooling = device.represent("lztemp_c")[1]
                    if not current_heating or not current_cooling:
                        raise HomeAssistantError(
                            "This device does not support zone temperature control. "
                            "The required temperature control parameters are not available."
                        )
                    current_heating[data.zone_id] = str(round(data.temperature))
                    current_cooling[data.zone_id] = str(round(data.temperature))
                    device.values["lztemp_h"] = quote(";".join(current_heating)).lower()
                    device.values["lztemp_c"] = quote(";".join(current_cooling)).lower()
                    path = "aircon/set_zone_setting"
                    params = {
                        "zone_name": current_state["zone_name"],
                        "zone_onoff": device.values["zone_onoff"],
                        "lztemp_c": device.values["lztemp_c"],
                        "lztemp_h": device.values["lztemp_h"],
                    }
                    params_str = "&".join(f"{k}={v}" for k, v in params.items())
                    path = f"{path}?{params_str}"
                    response = await device._get_resource(path)
                    if isinstance(response, str) and "ret=PARAM NG" in response:
                        raise HomeAssistantError(
                            "Failed to set zone temperature. The device may not support this operation."
                        )
                    # For any other response (including ret=OK), consider it a success
                    verify_state = await device._get_resource("aircon/get_zone_setting")
                    if verify_state:
                        device.values.update(verify_state)
                        if hasattr(coordinator, "async_request_refresh"):
                            await coordinator.async_request_refresh()
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
                            f"Failed to set zone temperature after {retries} attempts. "
                            "This device may not support zone temperature control."
                        ) from err
                    await asyncio.sleep(1)

        results = await asyncio.gather(
            *(
                set_temp(entry_id, coordinator)
                for entry_id, coordinator in coordinators.items()
            ),
            return_exceptions=True,
        )
        # Check for exceptions in results
        for result in results:
            if isinstance(result, Exception):
                raise result

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ZONE_TEMPERATURE,
        async_handle_set_zone_temperature,
        schema=SERVICE_SET_ZONE_TEMPERATURE_SCHEMA,
    )
    _LOGGER.info("Daikin custom services registered")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Daikin custom services."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_ZONE_TEMPERATURE)
    _services_registered.pop(hass, None)
    _LOGGER.info("Daikin custom services unregistered")
