"""UniFi Network services."""

from collections.abc import Mapping
from typing import Any

from aiounifi.models.client import ClientReconnectRequest, ClientRemoveRequest
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN as UNIFI_DOMAIN

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_REMOVE_CLIENTS = "remove_clients"

SERVICE_RECONNECT_CLIENT_SCHEMA = vol.All(
    vol.Schema({vol.Required(ATTR_DEVICE_ID): str})
)

SUPPORTED_SERVICES = (SERVICE_RECONNECT_CLIENT, SERVICE_REMOVE_CLIENTS)

SERVICE_TO_SCHEMA = {
    SERVICE_RECONNECT_CLIENT: SERVICE_RECONNECT_CLIENT_SCHEMA,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for UniFi integration."""

    services = {
        SERVICE_RECONNECT_CLIENT: async_reconnect_client,
        SERVICE_REMOVE_CLIENTS: async_remove_clients,
    }

    async def async_call_unifi_service(service_call: ServiceCall) -> None:
        """Call correct UniFi service."""
        await services[service_call.service](hass, service_call.data)

    for service in SUPPORTED_SERVICES:
        hass.services.async_register(
            UNIFI_DOMAIN,
            service,
            async_call_unifi_service,
            schema=SERVICE_TO_SCHEMA.get(service),
        )


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

    for entry in hass.config_entries.async_entries(UNIFI_DOMAIN):
        if (
            (hub := entry.runtime_data)
            and not hub.available
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
    for entry in hass.config_entries.async_entries(UNIFI_DOMAIN):
        if (hub := entry.runtime_data) and not hub.available:
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
