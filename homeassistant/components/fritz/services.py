"""Services for Fritz integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN, SERVICE_SET_GUEST_WIFI_PW
from .coordinator import AvmWrapper

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SCHEMA_SET_GUEST_WIFI_PW = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Optional("password"): vol.Length(min=8, max=63),
        vol.Optional("length"): vol.Range(min=8, max=63),
    }
)

SERVICE_LIST: list[tuple[str, vol.Schema | None]] = [
    (SERVICE_SET_GUEST_WIFI_PW, SERVICE_SCHEMA_SET_GUEST_WIFI_PW),
]


async def _async_call_fritz_service(service_call: ServiceCall) -> None:
    """Call correct Fritz service."""
    hass = service_call.hass
    target_entry_ids = await async_extract_config_entry_ids(hass, service_call)
    target_entries = [
        loaded_entry
        for loaded_entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if loaded_entry.entry_id in target_entry_ids
    ]

    if not target_entries:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"service": service_call.service},
        )

    for target_entry in target_entries:
        _LOGGER.debug("Executing service %s", service_call.service)
        avm_wrapper: AvmWrapper = hass.data[DOMAIN][target_entry.entry_id]
        await avm_wrapper.service_fritzbox(service_call, target_entry)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    for service, schema in SERVICE_LIST:
        hass.services.async_register(DOMAIN, service, _async_call_fritz_service, schema)
