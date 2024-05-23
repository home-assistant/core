"""Services for Fritz integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    DOMAIN,
    FRITZ_SERVICES,
    SERVICE_CLEANUP,
    SERVICE_REBOOT,
    SERVICE_RECONNECT,
    SERVICE_SET_GUEST_WIFI_PW,
)
from .coordinator import AvmWrapper

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA_SET_GUEST_WIFI_PW = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Optional("password"): vol.Length(min=8, max=63),
        vol.Optional("length"): vol.Range(min=8, max=63),
    }
)

SERVICE_LIST: list[tuple[str, vol.Schema | None]] = [
    (SERVICE_CLEANUP, None),
    (SERVICE_REBOOT, None),
    (SERVICE_RECONNECT, None),
    (SERVICE_SET_GUEST_WIFI_PW, SERVICE_SCHEMA_SET_GUEST_WIFI_PW),
]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    for service, _ in SERVICE_LIST:
        if hass.services.has_service(DOMAIN, service):
            return

    async def async_call_fritz_service(service_call: ServiceCall) -> None:
        """Call correct Fritz service."""

        if not (
            fritzbox_entry_ids := await _async_get_configured_avm_device(
                hass, service_call
            )
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
                translation_placeholders={"service": service_call.service},
            )

        for entry_id in fritzbox_entry_ids:
            _LOGGER.debug("Executing service %s", service_call.service)
            avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry_id]
            if config_entry := hass.config_entries.async_get_entry(entry_id):
                await avm_wrapper.service_fritzbox(service_call, config_entry)
            else:
                _LOGGER.error(
                    "Executing service %s failed, no config entry found",
                    service_call.service,
                )

    for service, schema in SERVICE_LIST:
        hass.services.async_register(DOMAIN, service, async_call_fritz_service, schema)


async def _async_get_configured_avm_device(
    hass: HomeAssistant, service_call: ServiceCall
) -> list:
    """Get FritzBoxTools class from config entry."""

    list_entry_id: list = []
    for entry_id in await async_extract_config_entry_ids(hass, service_call):
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if (
            config_entry
            and config_entry.domain == DOMAIN
            and config_entry.state == ConfigEntryState.LOADED
        ):
            list_entry_id.append(entry_id)
    return list_entry_id


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for Fritz integration."""

    if not hass.data.get(FRITZ_SERVICES):
        return

    hass.data[FRITZ_SERVICES] = False

    for service, _ in SERVICE_LIST:
        hass.services.async_remove(DOMAIN, service)
