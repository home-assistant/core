"""Services for the TP-Link Omada integration."""

from enum import StrEnum
from typing import cast

import probatio
from tplink_omada_client import OmadaClientSettings
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CommonServiceArgument
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


class OmadaService(StrEnum):
    """Store keys for TP-Link Omada services."""

    RECONNECT_CLIENT = "reconnect_client"
    SET_CLIENT_NAME = "set_client_name"


class OmadaServiceArgument(StrEnum):
    """Store keys for TP-Link Omada service arguments."""

    MAC = "mac"
    NAME = "name"


def _get_controller(call: ServiceCall) -> OmadaSiteController:
    if call.data.get(CommonServiceArgument.CONFIG_ENTRY_ID):
        entry = call.hass.config_entries.async_get_entry(
            call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
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

    mac: str = call.data[OmadaServiceArgument.MAC]

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

    entry = hass.config_entries.async_get_entry(
        call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
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

    device = dr.async_get(hass).async_get(call.data[CommonServiceArgument.DEVICE_ID])
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
    name: str = call.data[OmadaServiceArgument.NAME]

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
        OmadaService.SET_CLIENT_NAME,
        _handle_set_client_name,
        schema=probatio.Schema(
            {
                probatio.Required(
                    CommonServiceArgument.CONFIG_ENTRY_ID
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                probatio.Required(
                    CommonServiceArgument.DEVICE_ID
                ): selector.DeviceSelector(),
                probatio.Required(OmadaServiceArgument.NAME): probatio.All(
                    cv.string, probatio.NonEmpty()
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        OmadaService.RECONNECT_CLIENT,
        _handle_reconnect_client,
        schema=probatio.Schema(
            {
                probatio.Optional(
                    CommonServiceArgument.CONFIG_ENTRY_ID
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                probatio.Required(OmadaServiceArgument.MAC): cv.string,
            }
        ),
    )
