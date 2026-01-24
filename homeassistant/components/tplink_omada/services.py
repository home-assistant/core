"""Services for the TP-Link Omada integration."""

from typing import cast

from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)

from .const import DOMAIN
from .controller import OmadaSiteController

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_CLEANUP_CLIENT_TRACKERS = "cleanup_client_trackers"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_MAC = "mac"


def _get_controller(call: ServiceCall) -> tuple[OmadaSiteController, ConfigEntry]:
    """Get the controller and config entry from the service call."""
    if call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = call.hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )
        if not entry:
            raise ServiceValidationError("Specified TP-Link Omada controller not found")
    else:
        # Assume first loaded entry if none specified (for backward compatibility/99% use case)
        entries = call.hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 0:
            raise ServiceValidationError("No active TP-Link Omada controllers found")
        entry = entries[0]

    entry = cast(ConfigEntry[OmadaSiteController], entry)

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            "The TP-Link Omada integration is not currently available"
        )
    return entry.runtime_data, entry


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
    controller, _ = _get_controller(call)

    mac: str = call.data[ATTR_MAC]

    try:
        await controller.omada_client.reconnect_client(mac)
    except OmadaClientException as ex:
        raise HomeAssistantError(f"Failed to reconnect client with MAC {mac}") from ex


SCHEMA_CLEANUP_CLIENT_TRACKERS = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_ids,
    }
)


async def _handle_cleanup_client_trackers(call: ServiceCall) -> None:
    """Handle the service action to cleanup client tracker entities."""
    entity_registry = er.async_get(call.hass)

    # Get target entity_ids from the service call
    target_entity_ids = call.data.get("entity_id")
    if target_entity_ids is None:
        # If no target specified, process all tplink_omada device_trackers
        all_entries = call.hass.config_entries.async_entries(DOMAIN)
        entities_to_check = []
        for entry in all_entries:
            if entry.state != ConfigEntryState.LOADED:
                continue
            entities_to_check.extend(
                er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            )
    else:
        # Convert to list if single entity
        if isinstance(target_entity_ids, str):
            target_entity_ids = [target_entity_ids]

        # Get registry entries for specified entities
        entities_to_check = [
            entity
            for entity_id in target_entity_ids
            if (entity := entity_registry.async_get(entity_id)) is not None
        ]

    for entity in entities_to_check:
        # Only process device_tracker entities from this integration
        if entity.domain != "device_tracker" or entity.platform != "tplink_omada":
            continue

        # Extract MAC address from unique_id (format: "scanner_{site_id}_{mac}")
        if not entity.unique_id or not entity.unique_id.startswith("scanner_"):
            continue

        parts = entity.unique_id.split("_", 2)
        if len(parts) != 3:
            continue

        client_mac = parts[2]

        # Get the controller for this entity's config entry
        if not entity.config_entry_id:
            continue

        if not (
            entry := call.hass.config_entries.async_get_entry(entity.config_entry_id)
        ):
            continue
        if entry.state != ConfigEntryState.LOADED:
            continue

        controller = cast(OmadaSiteController, entry.runtime_data)

        # Get all known clients from this controller's Omada
        known_client_macs = {
            client.mac async for client in controller.omada_client.get_known_clients()
        }

        # If the client is not in the known clients list, remove the entity
        if client_mac not in known_client_macs:
            entity_registry.async_remove(entity.entity_id)


SERVICES = [
    (SERVICE_RECONNECT_CLIENT, SCHEMA_RECONNECT_CLIENT, _handle_reconnect_client),
    (
        SERVICE_CLEANUP_CLIENT_TRACKERS,
        SCHEMA_CLEANUP_CLIENT_TRACKERS,
        _handle_cleanup_client_trackers,
    ),
]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""

    for service_name, schema, handler in SERVICES:
        hass.services.async_register(DOMAIN, service_name, handler, schema=schema)
