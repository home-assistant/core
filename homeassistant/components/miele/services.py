"""Services for Miele integration."""

import logging
from typing import cast

import aiohttp
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import MieleConfigEntry

ATTR_PROGRAM_ID = "program_id"
ATTR_DURATION = "duration"

SERVICE_PROGRAM = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM_ID): cv.positive_int,
        vol.Optional(ATTR_DURATION): cv.positive_int,
        vol.Optional(ATTR_TEMPERATURE): cv.positive_int,
    },
)

_LOGGER = logging.getLogger(__name__)


async def extract_our_config_entry(service_call: ServiceCall) -> MieleConfigEntry:
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
            translation_key="set_program_no_device",
        )
    return target_entries[0]


async def set_program(call: ServiceCall) -> None:
    """Set a program on a Miele appliance."""

    _LOGGER.debug("Set program call: %s", call)
    config_entry = await extract_our_config_entry(call)
    device_reg = dr.async_get(call.hass)
    api = config_entry.runtime_data.api
    device = call.data[ATTR_DEVICE_ID]
    device_entry = device_reg.async_get(device)

    data = {"programId": call.data[ATTR_PROGRAM_ID]}
    if ATTR_DURATION in call.data:
        data[ATTR_DURATION] = [
            call.data[ATTR_DURATION] // 60,
            call.data[ATTR_DURATION] % 60,
        ]
    if ATTR_TEMPERATURE in call.data:
        data[ATTR_TEMPERATURE] = call.data[ATTR_TEMPERATURE]
    try:
        if serial_number := cast(dr.DeviceEntry, device_entry).serial_number:
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(DOMAIN, "set_program", set_program, SERVICE_PROGRAM)
