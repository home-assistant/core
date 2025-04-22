"""Services for Miele integration."""

import logging
from typing import cast

import aiohttp
import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN, PROGRAM_ID
from .coordinator import MieleConfigEntry

SERVICE_PROGRAM = cv.make_entity_service_schema(
    {
        vol.Required("program_id"): cv.positive_int,
        vol.Optional("duration"): cv.positive_int,
        vol.Optional("temperature"): cv.positive_int,
    },
)

_LOGGER = logging.getLogger(__name__)


async def extract_our_config_entry_ids(service_call: ServiceCall) -> MieleConfigEntry:
    """Extract config entry IDs from the service call."""
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
    config_entry = await extract_our_config_entry_ids(call)
    device_reg = dr.async_get(call.hass)
    api = cast(MieleConfigEntry, config_entry).runtime_data.api
    for device in call.data[CONF_DEVICE_ID]:
        device_entry = device_reg.async_get(device)

        data = {PROGRAM_ID: call.data["program_id"]}
        if "duration" in call.data:
            data["duration"] = [
                call.data["duration"] // 60,
                call.data["duration"] % 60,
            ]
        if "temperature" in call.data:
            data["temperature"] = call.data["temperature"]
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
