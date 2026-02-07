"""Cleanup helpers for the TP-Link Omada integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging

from tplink_omada_client.clients import OmadaWirelessClient
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .controller import OmadaSiteController

_LOGGER = logging.getLogger(__name__)

DEVICE_TRACKER_DOMAIN = "device_tracker"


def _unique_id_to_mac(unique_id: str | None) -> str | None:
    """Extract the client MAC address from a tracker unique ID."""
    if not unique_id or not unique_id.startswith("scanner_"):
        return None
    parts = unique_id.split("_", 2)
    if len(parts) != 3:
        return None
    return parts[2]


async def _async_get_known_wireless_client_macs(
    controller: OmadaSiteController,
) -> set[str]:
    """Return the set of wireless client MAC addresses known to the controller."""
    macs: set[str] = set()
    async for client in controller.omada_client.get_known_clients():
        if isinstance(client, OmadaWirelessClient):
            macs.add(client.mac)
    return macs


async def async_cleanup_client_trackers(
    hass: HomeAssistant,
    *,
    entity_ids: Iterable[str] | None = None,
    config_entry_ids: set[str] | None = None,
    raise_on_error: bool = False,
) -> None:
    """Remove stale client tracker entities for the Omada integration."""

    entity_registry = er.async_get(hass)
    allowed_states: set[ConfigEntryState] = {ConfigEntryState.LOADED}
    if config_entry_ids is not None:
        allowed_states.add(ConfigEntryState.SETUP_IN_PROGRESS)

    if entity_ids is not None:
        entities_to_check = [
            entity
            for entity_id in entity_ids
            if (entity := entity_registry.async_get(entity_id)) is not None
        ]
    else:
        if config_entry_ids is None:
            config_entry_ids = {
                entry.entry_id
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.state == ConfigEntryState.LOADED
            }
        entities_to_check = []
        for entry_id in config_entry_ids:
            entities_to_check.extend(
                er.async_entries_for_config_entry(entity_registry, entry_id)
            )

    controllers: dict[str, OmadaSiteController] = {}
    known_clients: dict[str, set[str]] = {}

    for entity in entities_to_check:
        if entity is None or entity.platform != DOMAIN:
            continue
        if entity.domain != DEVICE_TRACKER_DOMAIN or not entity.config_entry_id:
            continue

        client_mac = _unique_id_to_mac(entity.unique_id)
        if client_mac is None:
            continue

        entry_id = entity.config_entry_id
        if entry_id not in controllers:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is None
                or entry.state not in allowed_states
                or not isinstance(entry.runtime_data, OmadaSiteController)
            ):
                continue
            controllers[entry_id] = entry.runtime_data

        if entry_id not in known_clients:
            controller = controllers[entry_id]
            try:
                known_clients[entry_id] = await _async_get_known_wireless_client_macs(
                    controller
                )
            except OmadaClientException as ex:
                if raise_on_error:
                    raise HomeAssistantError(
                        "Failed to fetch Omada clients while cleaning trackers"
                    ) from ex
                _LOGGER.debug(
                    "Skipping stale client cleanup for entry %s: %s",
                    entry_id,
                    ex,
                )
                continue

        if client_mac not in known_clients[entry_id]:
            entity_registry.async_remove(entity.entity_id)


async def async_cleanup_devices(
    hass: HomeAssistant,
    *,
    config_entry_ids: set[str] | None = None,
) -> None:
    """Remove devices from the registry when Omada no longer reports them."""

    device_registry = dr.async_get(hass)

    allowed_states: set[ConfigEntryState] = {ConfigEntryState.LOADED}
    if config_entry_ids is None:
        config_entry_ids = {
            entry.entry_id
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state == ConfigEntryState.LOADED
        }
    else:
        allowed_states.add(ConfigEntryState.SETUP_IN_PROGRESS)

    for entry_id in config_entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.state not in allowed_states
            or not isinstance(entry.runtime_data, OmadaSiteController)
        ):
            continue

        controller = entry.runtime_data
        known_devices = controller.devices_coordinator.data

        registered_devices = device_registry.devices.get_devices_for_config_entry_id(
            entry_id
        )
        for device_entry in registered_devices:
            mac = next(
                (
                    identifier[1]
                    for identifier in device_entry.identifiers
                    if identifier[0] == DOMAIN
                ),
                None,
            )

            if mac and mac not in known_devices:
                _LOGGER.debug(
                    "Removing stale Omada device %s from entry %s",
                    mac,
                    entry_id,
                )
                device_registry.async_update_device(
                    device_entry.id,
                    remove_config_entry_id=entry_id,
                )
