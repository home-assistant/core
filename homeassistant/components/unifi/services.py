"""UniFi Network services."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import aiounifi
from aiounifi.models.client import ClientReconnectRequest, ClientRemoveRequest
import probatio

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, LOGGER
from .errors import controller_error_reason

if TYPE_CHECKING:
    from .hub import UnifiHub

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_REMOVE_CLIENTS = "remove_clients"
SERVICE_SET_WAN_FAILOVER_ORDER = "set_wan_failover_order"

# The controller rejects a duplicate priority with this message, there is no
# dedicated aiounifi exception for it.
ERROR_DUPLICATE_PRIORITY = "api.err.WanFailOverPriorityAlreadyExists"

SERVICE_RECONNECT_CLIENT_SCHEMA = probatio.All(
    probatio.Schema({probatio.Required(ATTR_DEVICE_ID): str})
)

SERVICE_SET_WAN_FAILOVER_ORDER_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_DEVICE_ID): probatio.All(
            probatio.EnsureList(),
            [cv.string],
            probatio.Length(min=1),
            probatio.Unique(),
        )
    }
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
            DOMAIN,
            service,
            async_call_unifi_service,
            schema=SERVICE_TO_SCHEMA.get(service),
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_WAN_FAILOVER_ORDER,
        async_set_wan_failover_order,
        schema=SERVICE_SET_WAN_FAILOVER_ORDER_SCHEMA,
    )


async def async_reconnect_client(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Try to get wireless client to reconnect to Wi-Fi."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(
        data[ATTR_DEVICE_ID], include_child_devices=False
    )

    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="reconnect_client_device_not_found",
        )

    mac = ""
    for connection in device_entry.connections:
        if connection[0] == CONNECTION_NETWORK_MAC:
            mac = connection[1]
            break

    if mac == "":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="reconnect_client_no_mac",
        )

    for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if (
            (not (hub := config_entry.runtime_data).available)
            or (client := hub.api.clients.get(mac)) is None
            or client.is_wired
        ):
            continue

        try:
            await hub.api.request(ClientReconnectRequest.create(mac))
        except aiounifi.AiounifiException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reconnect_client_request_failed",
            ) from err


async def async_remove_clients(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Remove select clients from UniFi Network.

    Validates based on:
    - Total time between first seen and last seen is less than 15 minutes.
    - Neither IP, hostname nor name is configured.
    """
    for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if not (hub := config_entry.runtime_data).available:
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
            try:
                await hub.api.request(ClientRemoveRequest.create(clients_to_remove))
            except aiounifi.AiounifiException as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="remove_clients_request_failed",
                ) from err


def _async_resolve_wan_network(
    hass: HomeAssistant, device_id: str
) -> tuple[UnifiHub, str]:
    """Resolve a device ID into the hub and network ID of a WAN network."""
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is not None:
        for identifier_domain, network_id in device_entry.identifiers:
            if identifier_domain != DOMAIN:
                continue
            for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
                hub = config_entry.runtime_data
                if (network := hub.api.networks.get(network_id)) is not None and (
                    network.is_wan
                ):
                    return hub, network_id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="wan_network_not_found",
        translation_placeholders={"device_id": device_id},
    )


async def _async_apply_failover_priorities(
    hub: UnifiHub, priorities: Mapping[str, int], park_priority: int
) -> None:
    """Apply failover priorities, parking the networks on free values first.

    The controller rejects a duplicate priority, so every network involved is
    first moved out of the way before the target priorities are assigned.
    """
    for offset, network_id in enumerate(priorities):
        await hub.api.networks.save(
            hub.api.networks[network_id], wan_failover_priority=park_priority + offset
        )

    for network_id, priority in priorities.items():
        await hub.api.networks.save(
            hub.api.networks[network_id], wan_failover_priority=priority
        )


async def async_set_wan_failover_order(service_call: ServiceCall) -> None:
    """Renumber the failover priority of WAN networks to the requested order."""
    hass = service_call.hass
    resolved = [
        _async_resolve_wan_network(hass, device_id)
        for device_id in service_call.data[ATTR_DEVICE_ID]
    ]

    if len({id(hub) for hub, _ in resolved}) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="wan_networks_multiple_hubs",
        )
    hub = resolved[0][0]

    targets = {network_id: order for order, (_, network_id) in enumerate(resolved, 1)}
    original: dict[str, int] = {}
    for network_id in targets:
        if (priority := hub.api.networks[network_id].wan_failover_priority) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="wan_failover_priority_unsupported",
            )
        original[network_id] = priority

    priorities = [net.wan_failover_priority or 0 for net in hub.api.networks.values()]
    park_priority = max([*priorities, len(targets)]) + 1

    try:
        await _async_apply_failover_priorities(hub, targets, park_priority)
    except aiounifi.AiounifiException as err:
        try:
            await _async_apply_failover_priorities(
                hub, original, park_priority + len(targets)
            )
        except aiounifi.AiounifiException as rollback_err:
            LOGGER.error(
                "Failed to restore UniFi WAN failover priorities: %s", rollback_err
            )
        if controller_error_reason(err) == ERROR_DUPLICATE_PRIORITY:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="wan_failover_priority_conflict",
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_wan_failover_order_failed",
            translation_placeholders={"reason": controller_error_reason(err)},
        ) from err
