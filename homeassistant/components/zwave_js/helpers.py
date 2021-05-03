"""Helper functions for Z-Wave JS integration."""
from __future__ import annotations

from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg

from .const import CONF_DATA_COLLECTION_OPTED_IN, DATA_CLIENT, DOMAIN


@callback
def get_value_of_zwave_value(value: ZwaveValue | None) -> Any | None:
    """Return the value of a ZwaveValue."""
    return value.value if value else None


async def async_enable_statistics(client: ZwaveClient) -> None:
    """Enable statistics on the driver."""
    await client.driver.async_enable_statistics("Home Assistant", HA_VERSION)


@callback
def update_data_collection_preference(
    hass: HomeAssistant, entry: ConfigEntry, preference: bool
) -> None:
    """Update data collection preference on config entry."""
    new_data = entry.data.copy()
    new_data[CONF_DATA_COLLECTION_OPTED_IN] = preference
    hass.config_entries.async_update_entry(entry, data=new_data)


@callback
def get_unique_id(home_id: str, value_id: str) -> str:
    """Get unique ID from home ID and value ID."""
    return f"{home_id}.{value_id}"


@callback
def get_device_id(client: ZwaveClient, node: ZwaveNode) -> tuple[str, str]:
    """Get device registry identifier for Z-Wave node."""
    return (DOMAIN, f"{client.driver.controller.home_id}-{node.node_id}")


@callback
def get_home_and_node_id_from_device_id(device_id: tuple[str, ...]) -> list[str]:
    """
    Get home ID and node ID for Z-Wave device registry entry.

    Returns [home_id, node_id]
    """
    return device_id[1].split("-")


@callback
def async_get_node_from_device_id(hass: HomeAssistant, device_id: str) -> ZwaveNode:
    """
    Get node from a device ID.

    Raises ValueError if device is invalid or node can't be found.
    """
    device_entry = async_get_dev_reg(hass).async_get(device_id)

    if not device_entry:
        raise ValueError("Device ID is not valid")

    # Use device config entry ID's to validate that this is a valid zwave_js device
    # and to get the client
    config_entry_ids = device_entry.config_entries
    config_entry_id = next(
        (
            config_entry_id
            for config_entry_id in config_entry_ids
            if cast(
                ConfigEntry,
                hass.config_entries.async_get_entry(config_entry_id),
            ).domain
            == DOMAIN
        ),
        None,
    )
    if config_entry_id is None or config_entry_id not in hass.data[DOMAIN]:
        raise ValueError("Device is not from an existing zwave_js config entry")

    client = hass.data[DOMAIN][config_entry_id][DATA_CLIENT]

    # Get node ID from device identifier, perform some validation, and then get the
    # node
    identifier = next(
        (
            get_home_and_node_id_from_device_id(identifier)
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )

    node_id = int(identifier[1]) if identifier is not None else None

    if node_id is None or node_id not in client.driver.controller.nodes:
        raise ValueError("Device node can't be found")

    return client.driver.controller.nodes[node_id]


@callback
def async_get_node_from_entity_id(hass: HomeAssistant, entity_id: str) -> ZwaveNode:
    """
    Get node from an entity ID.

    Raises ValueError if entity is invalid.
    """
    entity_entry = async_get_ent_reg(hass).async_get(entity_id)

    if not entity_entry:
        raise ValueError("Entity ID is not valid")

    if entity_entry.platform != DOMAIN:
        raise ValueError("Entity is not from zwave_js integration")

    # Assert for mypy, safe because we know that zwave_js entities are always
    # tied to a device
    assert entity_entry.device_id
    return async_get_node_from_device_id(hass, entity_entry.device_id)
