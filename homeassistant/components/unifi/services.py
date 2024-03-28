"""UniFi Network services."""

from collections.abc import Mapping
import logging
from typing import Any, Final, Union

from aiounifi.models.client import ClientReconnectRequest, ClientRemoveRequest
from aiounifi.models.wlan import Wlan, WlanChangePasswordRequest
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN as UNIFI_DOMAIN
from .hub import UnifiHub

_LOGGER: Final = logging.getLogger(__name__)

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_REMOVE_CLIENTS = "remove_clients"
SERVICE_CHANGE_WLAN_PASSWORD = "change_wlan_password"
SERVICE_GET_WLAN_PASSWORD = "get_wlan_password"

SERVICE_RECONNECT_CLIENT_SCHEMA = vol.All(
    vol.Schema({vol.Required(ATTR_DEVICE_ID): str})
)

SERVICE_CHANGE_WLAN_PASSWORD_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("hub_name"): str,
            vol.Required("wlan_name"): str,
            vol.Required("new_password"): str,
        }
    )
)

SERVICE_GET_WLAN_PASSWORD_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("hub_name"): str,
            vol.Required("wlan_name"): str,
        }
    )
)

SUPPORTED_SERVICES = (
    SERVICE_RECONNECT_CLIENT,
    SERVICE_REMOVE_CLIENTS,
    SERVICE_CHANGE_WLAN_PASSWORD,
    SERVICE_GET_WLAN_PASSWORD,
)

SERVICE_RESPONSE = {
    SERVICE_RECONNECT_CLIENT: SupportsResponse.NONE,
    SERVICE_REMOVE_CLIENTS: SupportsResponse.NONE,
    SERVICE_CHANGE_WLAN_PASSWORD: SupportsResponse.NONE,
    SERVICE_GET_WLAN_PASSWORD: SupportsResponse.ONLY,
}

SERVICE_TO_SCHEMA = {
    SERVICE_RECONNECT_CLIENT: SERVICE_RECONNECT_CLIENT_SCHEMA,
    SERVICE_CHANGE_WLAN_PASSWORD: SERVICE_CHANGE_WLAN_PASSWORD_SCHEMA,
    SERVICE_GET_WLAN_PASSWORD: SERVICE_GET_WLAN_PASSWORD_SCHEMA,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for UniFi integration."""

    services = {
        SERVICE_RECONNECT_CLIENT: async_reconnect_client,
        SERVICE_REMOVE_CLIENTS: async_remove_clients,
        SERVICE_CHANGE_WLAN_PASSWORD: async_change_wlan_password,
        SERVICE_GET_WLAN_PASSWORD: async_get_wlan_password,
    }

    async def async_call_unifi_service(
        service_call: ServiceCall,
    ) -> Union[ServiceResponse, None]:
        """Call correct UniFi service."""
        return await services[service_call.service](hass, service_call.data)

    for service in SUPPORTED_SERVICES:
        hass.services.async_register(
            UNIFI_DOMAIN,
            service,
            async_call_unifi_service,
            schema=SERVICE_TO_SCHEMA.get(service),
            supports_response=SERVICE_RESPONSE.get(service, SupportsResponse.NONE),
        )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unload UniFi Network services."""
    for service in SUPPORTED_SERVICES:
        hass.services.async_remove(UNIFI_DOMAIN, service)


async def async_reconnect_client(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Try to get wireless client to reconnect to Wi-Fi."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(data[ATTR_DEVICE_ID])

    if device_entry is None:
        return

    mac = ""
    for connection in device_entry.connections:
        if connection[0] == CONNECTION_NETWORK_MAC:
            mac = connection[1]
            break

    if mac == "":
        return

    for hub in hass.data[UNIFI_DOMAIN].values():
        if (
            not hub.available
            or (client := hub.api.clients.get(mac)) is None
            or client.is_wired
        ):
            continue

        await hub.api.request(ClientReconnectRequest.create(mac))


async def async_remove_clients(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Remove select clients from UniFi Network.

    Validates based on:
    - Total time between first seen and last seen is less than 15 minutes.
    - Neither IP, hostname nor name is configured.
    """
    for hub in hass.data[UNIFI_DOMAIN].values():
        if not hub.available:
            continue

        clients_to_remove = []

        for client in hub.api.clients_all.values():
            if (
                client.last_seen
                and client.first_seen
                and client.last_seen - client.first_seen > 900
            ):
                continue

            if any({client.fixed_ip, client.hostname, client.name}):
                continue

            clients_to_remove.append(client.mac)

        if clients_to_remove:
            await hub.api.request(ClientRemoveRequest.create(clients_to_remove))


async def find_hub_by_name(hass: HomeAssistant, hub_name: str) -> Union[UnifiHub, None]:
    """Find a hub by its name."""
    hub = next(
        (
            hub
            for hub in hass.data[UNIFI_DOMAIN].values()
            if hub.config.entry.title == hub_name
        ),
        None,
    )
    if hub is None:
        _LOGGER.error("Hub '%s' not found", hub_name)
    return hub


async def find_wlan_by_name(hub: UnifiHub, wlan_name: str) -> Union[Wlan, None]:
    """Find a WLAN by its name."""
    for wlan in hub.api.wlans.values():
        if wlan.name == wlan_name:
            return wlan
    _LOGGER.error(
        "WLAN '%s' not found in the Hub '%s'", wlan_name, hub.config.entry.title
    )
    return None


async def async_change_wlan_password(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> None:
    """Change the password for a given WLAN Name for a given Hub."""
    hub_name = data["hub_name"]
    wlan_name = data["wlan_name"]
    new_password = data["new_password"]

    hub = await find_hub_by_name(hass, hub_name)
    if hub is None:
        return

    wlan = await find_wlan_by_name(hub, wlan_name)
    if wlan is None:
        return None

    try:
        await hub.api.request(WlanChangePasswordRequest.create(wlan.id, new_password))
        _LOGGER.info(
            "Password for WLAN Name '%s' changed in Hub '%s' successfully",
            wlan_name,
            hub_name,
        )
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Failed to change password for WLAN Name '%s' in Hub '%s': %s",
            wlan_name,
            hub_name,
            e,
        )


async def async_get_wlan_password(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> ServiceResponse:
    """Retrieve the password for a given WLAN Name for a given Hub."""
    hub_name = data["hub_name"]
    wlan_name = data["wlan_name"]

    hub = await find_hub_by_name(hass, hub_name)
    if hub is None:
        return {}

    wlan = await find_wlan_by_name(hub, wlan_name)
    if wlan is None:
        return {}

    _LOGGER.info(
        "Retrieved password for WLAN Name '%s' in Hub '%s' successfully",
        wlan_name,
        hub_name,
    )

    return {"password": wlan.x_passphrase}
