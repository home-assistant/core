"""UniFi services."""

from .const import DOMAIN as UNIFI_DOMAIN

UNIFI_SERVICES = "unifi_services"

SERVICE_REMOVE_CLIENTS = "remove_clients"


async def async_setup_services(hass) -> None:
    """Set up services for UniFi integration."""
    if hass.data.get(UNIFI_SERVICES, False):
        return

    hass.data[UNIFI_SERVICES] = True

    async def async_call_unifi_service(service_call) -> None:
        """Call correct UniFi service."""
        service = service_call.service
        service_data = service_call.data

        controllers = hass.data[UNIFI_DOMAIN].values()

        if service == SERVICE_REMOVE_CLIENTS:
            await async_remove_clients(controllers, service_data)

    hass.services.async_register(
        UNIFI_DOMAIN,
        SERVICE_REMOVE_CLIENTS,
        async_call_unifi_service,
    )


async def async_unload_services(hass) -> None:
    """Unload UniFi services."""
    if not hass.data.get(UNIFI_SERVICES):
        return

    hass.data[UNIFI_SERVICES] = False

    hass.services.async_remove(UNIFI_DOMAIN, SERVICE_REMOVE_CLIENTS)


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
