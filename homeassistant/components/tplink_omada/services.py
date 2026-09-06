"""Services for the TP-Link Omada integration."""

from typing import cast

from tplink_omada_client import OmadaClientSettings
from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
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
            }
        ),
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
    }
)


def _get_client_mac(call: ServiceCall) -> str:
    """Return the network MAC address of the device referenced by the call."""
    device = dr.async_get(call.hass).async_get(call.data[ATTR_DEVICE_ID])
    if device is None or not isinstance(device, dr.DeviceEntry):
        # Child devices carry no connections to resolve a MAC from.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_not_found",
        )
    for connection_type, connection_id in device.connections:
        if connection_type == dr.CONNECTION_NETWORK_MAC:
            return connection_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="client_device_no_mac",
    )


async def _handle_set_client_name(call: ServiceCall) -> None:
    """Handle the service action to set the name of a network client."""
    controller = _get_controller(call)

    mac = _get_client_mac(call)
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
