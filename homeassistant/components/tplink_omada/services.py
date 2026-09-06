"""Services for the TP-Link Omada integration."""

from typing import cast

from tplink_omada_client import OmadaClientSettings
from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .controller import OmadaSiteController

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_SET_CLIENT_NAME = "set_client_name"

ATTR_MAC = "mac"


def _get_controller(call: ServiceCall) -> OmadaSiteController:
    if call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = call.hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )
        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="controller_not_found",
            )
    else:
        # Assume first loaded entry if none specified
        # (for backward compatibility/99% use case)
        entries = call.hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_controllers",
            )
        entry = entries[0]

    entry = cast(ConfigEntry[OmadaSiteController], entry)

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_unavailable",
        )
    return entry.runtime_data


SCHEMA_RECONNECT_CLIENT = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_MAC): cv.string,
    }
)


async def _handle_reconnect_client(call: ServiceCall) -> None:
    """Handle the service action to force reconnection of a network client."""
    controller = _get_controller(call)

    mac: str = call.data[ATTR_MAC]

    try:
        await controller.omada_client.reconnect_client(mac)
    except OmadaClientException as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="reconnect_failed",
            translation_placeholders={"mac": mac},
        ) from ex


SCHEMA_SET_CLIENT_NAME = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_DEVICE_ID): selector.DeviceSelector(
            {
                "integration": DOMAIN,
                "entity": [
                    {
                        "domain": DEVICE_TRACKER_DOMAIN,
                        "integration": DOMAIN,
                    }
                ],
            }
        ),
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
    }
)


def _omada_tracker_entry_ids(hass: HomeAssistant, device: dr.DeviceEntry) -> set[str]:
    """Return the Omada config entries with a device tracker on the device."""
    omada_entry_ids = {
        entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)
    }
    return {
        entity.config_entry_id
        for entity in er.async_entries_for_device(er.async_get(hass), device.id)
        if entity.domain == DEVICE_TRACKER_DOMAIN
        and entity.config_entry_id in omada_entry_ids
    }


def _resolve_client_controller(
    call: ServiceCall,
) -> tuple[OmadaSiteController, str]:
    """Resolve the controller and MAC of the client referenced by the call."""
    hass = call.hass

    if not hass.config_entries.async_entries(DOMAIN):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_controllers",
        )

    requested_entry: ConfigEntry[OmadaSiteController] | None = None
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="controller_not_found",
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="controller_unavailable",
            )
        requested_entry = cast(ConfigEntry[OmadaSiteController], entry)

    device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    if device is None or not isinstance(device, dr.DeviceEntry):
        # Child devices carry no connections to resolve a MAC from.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_not_found",
        )

    tracker_entry_ids = _omada_tracker_entry_ids(hass, device)
    if not tracker_entry_ids:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_not_tracked",
        )

    if requested_entry is None:
        entry = next(
            entry
            for entry_id in tracker_entry_ids
            if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="controller_unavailable",
            )
        controller = cast(ConfigEntry[OmadaSiteController], entry).runtime_data
    elif requested_entry.entry_id not in tracker_entry_ids:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_mismatch",
        )
    else:
        controller = requested_entry.runtime_data

    for connection_type, connection_id in device.connections:
        if connection_type == dr.CONNECTION_NETWORK_MAC:
            return controller, connection_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="client_device_no_mac",
    )


async def _handle_set_client_name(call: ServiceCall) -> None:
    """Handle the service action to set the name of a network client."""
    controller, mac = _resolve_client_controller(call)
    name: str = call.data[ATTR_NAME]

    try:
        await controller.omada_client.update_client(mac, OmadaClientSettings(name=name))
    except OmadaClientException as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_client_name_failed",
            translation_placeholders={"mac": mac},
        ) from ex


SERVICES = [
    (
        SERVICE_RECONNECT_CLIENT,
        SCHEMA_RECONNECT_CLIENT,
        _handle_reconnect_client,
        False,
    ),
    (
        SERVICE_SET_CLIENT_NAME,
        SCHEMA_SET_CLIENT_NAME,
        _handle_set_client_name,
        True,
    ),
]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""

    for service_name, schema, handler, admin_only in SERVICES:
        if admin_only:
            async_register_admin_service(
                hass, DOMAIN, service_name, handler, schema=schema
            )
        else:
            hass.services.async_register(DOMAIN, service_name, handler, schema=schema)
