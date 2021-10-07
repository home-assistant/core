"""UniFi services."""

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN as UNIFI_DOMAIN

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_REMOVE_CLIENTS = "remove_clients"

SERVICE_RECONNECT_CLIENT_SCHEMA = vol.All(
    vol.Schema({vol.Required(ATTR_DEVICE_ID): str})
)


@callback
def async_setup_services(hass) -> None:
    """Set up services for UniFi integration."""

    async def async_call_unifi_service(service_call) -> None:
        """Call correct UniFi service."""
        service = service_call.service
        service_data = service_call.data

        controllers = hass.data[UNIFI_DOMAIN].values()

        if service == SERVICE_RECONNECT_CLIENT:
            await async_reconnect_client(hass, service_data)

        elif service == SERVICE_REMOVE_CLIENTS:
            await async_remove_clients(controllers, service_data)

    hass.services.async_register(
        UNIFI_DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        async_call_unifi_service,
        schema=SERVICE_RECONNECT_CLIENT_SCHEMA,
    )

    hass.services.async_register(
        UNIFI_DOMAIN,
        SERVICE_REMOVE_CLIENTS,
        async_call_unifi_service,
    )


@callback
def async_unload_services(hass) -> None:
    """Unload UniFi services."""
    hass.services.async_remove(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS)


async def async_reconnect_client(hass, data) -> None:
    """Try to get wireless client to reconnect to Wi-Fi."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    entry = device_registry.async_get(data[ATTR_DEVICE_ID])

    mac = ""
    for connection in entry.connections:
        if connection[0] == CONNECTION_NETWORK_MAC:
            mac = connection[1]
            break

    if mac == "":
        return

    for controller in hass.data[UNIFI_DOMAIN].values():
        if (
            controller.config_entry_id not in entry.config_entries
            or (client := controller.api.clients.get(mac)) is None
            or client.is_wired
        ):
            continue

        await controller.api.clients.async_reconnect(mac)


async def async_remove_clients(controllers, data) -> None:
    """Remove select clients from controller.

    Validates based on:
    - Total time between first seen and last seen is less than 15 minutes.
    - Neither IP, hostname nor name is configured.
    """
    for controller in controllers:

        if not controller.available:
            continue

        clients_to_remove = []

        for client in controller.api.clients_all.values():

            if client.last_seen - client.first_seen > 900:
                continue

            if any({client.fixed_ip, client.hostname, client.name}):
                continue

            clients_to_remove.append(client.mac)

        if clients_to_remove:
            await controller.api.clients.remove_clients(macs=clients_to_remove)
