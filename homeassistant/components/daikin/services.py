"""Custom services for the Daikin integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any
from urllib.parse import quote
from weakref import WeakKeyDictionary

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids

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
        vol.Required("zone_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
        vol.Required("temperature"): vol.Coerce(float),
        vol.Optional("entry_id"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


async def _async_resolve_coordinators(
    hass: HomeAssistant, call: ServiceCall, data: SetZoneTemperatureData
) -> dict[str, Any]:
    """Return coordinators matching the service target."""
    daikin_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    coordinators: dict[str, Any] = {}

    if data.entry_id:
        if coordinator := daikin_data.get(data.entry_id):
            coordinators[data.entry_id] = coordinator
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_entry_not_found",
                translation_placeholders={"entry_id": data.entry_id},
            )
        return coordinators

    referenced_entry_ids: set[str] = set()
    entity_ids = await async_extract_entity_ids(hass, call)
    if entity_ids:
        entity_registry = er.async_get(hass)
        for entity_id in entity_ids:
            if (
                (entity_entry := entity_registry.async_get(entity_id))
                and entity_entry.config_entry_id
                and entity_entry.config_entry_id in daikin_data
            ):
                referenced_entry_ids.add(entity_entry.config_entry_id)

    match_attr = call.data.get(ATTR_ENTITY_ID)
    if match_attr == ENTITY_MATCH_ALL:
        referenced_entry_ids = set(daikin_data)
    elif match_attr == ENTITY_MATCH_NONE:
        referenced_entry_ids = set()

    if not referenced_entry_ids and len(daikin_data) == 1:
        referenced_entry_ids = set(daikin_data)

    for entry_id in referenced_entry_ids:
        if coordinator := daikin_data.get(entry_id):
            coordinators[entry_id] = coordinator

    return coordinators


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

        coordinators = await _async_resolve_coordinators(hass, call, data)

        if not coordinators:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_target_not_found",
            )

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
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="zone_inactive",
                        translation_placeholders={"zone_id": str(data.zone_id)},
                    )
            except IndexError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="zone_missing",
                    translation_placeholders={
                        "zone_id": str(data.zone_id),
                        "max_zone": str(len(zones) - 1),
                    },
                ) from err
            try:
                target_temp = device.target_temperature
            except AttributeError:
                target_temp = 22
            min_temp, max_temp = target_temp - 2, target_temp + 2
            if not (min_temp <= data.temperature <= max_temp):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="temperature_out_of_range",
                    translation_placeholders={
                        "temperature": f"{data.temperature:g}",
                        "min_temp": f"{min_temp:g}",
                        "max_temp": f"{max_temp:g}",
                    },
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
                            translation_domain=DOMAIN,
                            translation_key="zone_settings_unavailable",
                        )
                    device.values.update(current_state)
                    current_heating = device.represent("lztemp_h")[1]
                    current_cooling = device.represent("lztemp_c")[1]
                    if not current_heating or not current_cooling:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="zone_parameters_unavailable",
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
                            translation_domain=DOMAIN,
                            translation_key="zone_set_failed",
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
                            translation_domain=DOMAIN,
                            translation_key="zone_set_retries_exceeded",
                            translation_placeholders={"retries": str(retries)},
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
