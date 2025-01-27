"""Services for Fritz integration."""

import logging

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzwlan import DEFAULT_PASSWORD_LENGTH
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import AvmWrapper

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_GUEST_WIFI_PW = "set_guest_wifi_password"
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
        try:
            if service_call.service == SERVICE_SET_GUEST_WIFI_PW:
                await avm_wrapper.async_trigger_set_guest_password(
                    service_call.data.get("password"),
                    service_call.data.get("length", DEFAULT_PASSWORD_LENGTH),
                )
                return

        except (FritzServiceError, FritzActionError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_parameter_unknown"
            ) from ex
        except FritzConnectionException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="service_not_supported"
            ) from ex


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    for service, schema in SERVICE_LIST:
        hass.services.async_register(DOMAIN, service, _async_call_fritz_service, schema)
