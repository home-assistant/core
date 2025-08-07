"""Services for Miele integration."""

from datetime import timedelta
import logging
from typing import cast

import aiohttp
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_TEMPERATURE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import MieleConfigEntry

ATTR_PROGRAM_ID = "program_id"
ATTR_DURATION = "duration"


SERVICE_SET_PROGRAM = "set_program"
SERVICE_SET_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM_ID): cv.positive_int,
    },
)

SERVICE_SET_PROGRAM_OVEN = "set_program_oven"
SERVICE_SET_PROGRAM_OVEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM_ID): cv.positive_int,
        vol.Optional(ATTR_TEMPERATURE): cv.positive_int,
        vol.Optional(ATTR_DURATION): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(minutes=1), max=timedelta(hours=12)),
        ),
    },
)

SERVICE_GET_PROGRAMS = "get_programs"
SERVICE_GET_PROGRAMS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
    },
)

_LOGGER = logging.getLogger(__name__)


async def _extract_config_entry(service_call: ServiceCall) -> MieleConfigEntry:
    """Extract config entry from the service call."""
    hass = service_call.hass
    target_entry_ids = await async_extract_config_entry_ids(hass, service_call)
    target_entries: list[MieleConfigEntry] = [
        loaded_entry
        for loaded_entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if loaded_entry.entry_id in target_entry_ids
    ]
    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return target_entries[0]


async def _get_serial_number(call: ServiceCall) -> str:
    """Extract the serial number from the device identifier."""

    device_reg = dr.async_get(call.hass)
    device = call.data[ATTR_DEVICE_ID]
    device_entry = device_reg.async_get(device)
    serial_number = next(
        (
            identifier[1]
            for identifier in cast(dr.DeviceEntry, device_entry).identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if serial_number is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )
    return serial_number


async def set_program(call: ServiceCall) -> None:
    """Set a program on a Miele appliance."""

    _LOGGER.debug("Set program call: %s", call)
    config_entry = await _extract_config_entry(call)
    api = config_entry.runtime_data.api

    serial_number = await _get_serial_number(call)
    data = {"programId": call.data[ATTR_PROGRAM_ID]}
    try:
        await api.set_program(serial_number, data)
    except aiohttp.ClientResponseError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_program_error",
            translation_placeholders={
                "status": str(ex.status),
                "message": ex.message,
            },
        ) from ex


async def set_program_oven(call: ServiceCall) -> None:
    """Set a program on a Miele oven."""

    _LOGGER.debug("Set program call: %s", call)
    config_entry = await _extract_config_entry(call)
    api = config_entry.runtime_data.api

    serial_number = await _get_serial_number(call)
    data = {"programId": call.data[ATTR_PROGRAM_ID]}
    if call.data.get(ATTR_DURATION) is not None:
        td = call.data[ATTR_DURATION]
        data["duration"] = [
            td.seconds // 3600,  # hours
            (td.seconds // 60) % 60,  # minutes
        ]
    if call.data.get(ATTR_TEMPERATURE) is not None:
        data["temperature"] = call.data[ATTR_TEMPERATURE]
    try:
        await api.set_program(serial_number, data)
    except aiohttp.ClientResponseError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_program_oven_error",
            translation_placeholders={
                "status": str(ex.status),
                "message": ex.message,
            },
        ) from ex


async def get_programs(call: ServiceCall) -> ServiceResponse:
    """Get available programs from appliance."""

    config_entry = await _extract_config_entry(call)
    api = config_entry.runtime_data.api
    serial_number = await _get_serial_number(call)

    try:
        programs = await api.get_programs(serial_number)
    except aiohttp.ClientResponseError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="get_programs_error",
            translation_placeholders={
                "status": str(ex.status),
                "message": ex.message,
            },
        ) from ex

    return {
        "programs": [
            {
                "program_id": item["programId"],
                "program": item["program"].strip(),
                "parameters": (
                    {
                        "temperature": (
                            {
                                "min": item["parameters"]["temperature"]["min"],
                                "max": item["parameters"]["temperature"]["max"],
                                "step": item["parameters"]["temperature"]["step"],
                                "mandatory": item["parameters"]["temperature"][
                                    "mandatory"
                                ],
                            }
                            if "temperature" in item["parameters"]
                            else {}
                        ),
                        "duration": (
                            {
                                "min": {
                                    "hours": item["parameters"]["duration"]["min"][0],
                                    "minutes": item["parameters"]["duration"]["min"][1],
                                },
                                "max": {
                                    "hours": item["parameters"]["duration"]["max"][0],
                                    "minutes": item["parameters"]["duration"]["max"][1],
                                },
                                "mandatory": item["parameters"]["duration"][
                                    "mandatory"
                                ],
                            }
                            if "duration" in item["parameters"]
                            else {}
                        ),
                    }
                    if item.get("parameters")
                    else {}
                ),
            }
            for item in programs
        ],
    }


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROGRAM,
        set_program,
        SERVICE_SET_PROGRAM_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROGRAM_OVEN,
        set_program_oven,
        SERVICE_SET_PROGRAM_OVEN_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PROGRAMS,
        get_programs,
        SERVICE_GET_PROGRAMS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
