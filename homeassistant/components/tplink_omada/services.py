"""Services for the TP-Link Omada integration."""

from typing import cast

from tplink_omada_client import OmadaClientSettings
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed
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


def _controller_mac(mac: str) -> str:
    """Normalize a registry MAC to the controller's canonical format."""
    return mac.upper().replace(":", "-")


async def _resolve_client_controller(
    call: ServiceCall,
) -> tuple[OmadaSiteController, str]:
    """Resolve the controller and MAC of the client referenced by the call."""
    hass = call.hass

    entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
    if not entry or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_not_found",
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_unavailable",
        )
    controller = cast(ConfigEntry[OmadaSiteController], entry).runtime_data

    device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    if device is None or not isinstance(device, dr.DeviceEntry):
        # Child devices carry no connections to resolve a MAC from.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_not_found",
        )

    macs = [
        connection_id
        for connection_type, connection_id in device.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    ]
    if not macs:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_no_mac",
        )

    known_macs: list[str] = []
    for mac in macs:
        controller_mac = _controller_mac(mac)
        try:
            await controller.omada_client.get_client(controller_mac)
        except RequestFailed as ex:
            # -41011 is the controller's "client not found" code (no public accessor).
            if getattr(ex, "_error_code", None) == -41011:
                continue
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="client_query_failed",
                translation_placeholders={"mac": controller_mac},
            ) from ex
        except OmadaClientException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="client_query_failed",
                translation_placeholders={"mac": controller_mac},
            ) from ex
        known_macs.append(controller_mac)

    if len(known_macs) == 1:
        return controller, known_macs[0]
    if not known_macs:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="client_device_not_tracked",
        )
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="client_mac_ambiguous",
    )


async def _handle_set_client_name(call: ServiceCall) -> None:
    """Handle the service action to set the name of a network client."""
    controller, mac = await _resolve_client_controller(call)
    name: str = call.data[ATTR_NAME]

    try:
        await controller.omada_client.update_client(mac, OmadaClientSettings(name=name))
    except OmadaClientException as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_client_name_failed",
            translation_placeholders={"mac": mac},
        ) from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""

    async_register_admin_service(
        hass,
        DOMAIN,
        "set_client_name",
        _handle_set_client_name,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(ATTR_DEVICE_ID): selector.DeviceSelector(),
                vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "reconnect_client",
        _handle_reconnect_client,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(ATTR_MAC): cv.string,
            }
        ),
    )
