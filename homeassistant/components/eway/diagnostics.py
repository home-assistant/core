"""Diagnostics support for Eway integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import EwayDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EwayDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get device registry
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Find the device for this config entry
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    # Collect device information
    devices_info = []
    for device_entry in device_entries:
        device_info: dict[str, Any] = {
            "id": device_entry.id,
            "name": device_entry.name,
            "model": device_entry.model,
            "manufacturer": device_entry.manufacturer,
            "sw_version": device_entry.sw_version,
            "hw_version": device_entry.hw_version,
            "identifiers": list(device_entry.identifiers),
            "connections": list(device_entry.connections),
            "via_device_id": device_entry.via_device_id,
            "disabled_by": device_entry.disabled_by,
            "configuration_url": device_entry.configuration_url,
        }

        # Get entities for this device
        entities = er.async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        )

        device_entities = []
        for entity in entities:
            entity_info: dict[str, Any] = {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "platform": entity.platform,
                "device_class": entity.device_class,
                "unit_of_measurement": entity.unit_of_measurement,
                "disabled_by": entity.disabled_by,
                "entity_category": entity.entity_category,
                "unique_id": entity.unique_id,
            }

            # Get current state if entity is enabled
            if not entity.disabled_by:
                state = hass.states.get(entity.entity_id)
                if state:
                    entity_info["state"] = {
                        "state": state.state,
                        "attributes": dict(state.attributes),
                        "last_changed": state.last_changed.isoformat(),
                        "last_updated": state.last_updated.isoformat(),
                    }

            device_entities.append(entity_info)

        device_info["entities_info"] = device_entities
        devices_info.append(device_info)

    # Prepare configuration data (remove sensitive information)
    config_data = dict(entry.data)
    # Remove sensitive MQTT credentials
    config_data.pop("mqtt_password", None)
    config_data.pop("mqtt_username", None)

    # Get coordinator data
    coordinator_data: dict[str, Any] = {
        "last_update_success": coordinator.last_update_success,
        "last_update_time": coordinator.last_update_success_time.isoformat()
        if coordinator.last_update_success_time
        else None,
        "update_interval": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "data_available": coordinator.data is not None,
    }

    # Add current data (if available)
    if coordinator.data:
        coordinator_data["current_data"] = coordinator.data

    # Add coordinator connection info
    coordinator_info = {
        "device_id": coordinator.device_id,
        "device_sn": coordinator.device_sn,
        "device_model": coordinator.device_model,
        "mqtt_host": coordinator.mqtt_host,
        "mqtt_port": coordinator.mqtt_port,
        "keepalive": coordinator.keepalive,
        "client_connected": coordinator.client_connected,
    }

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "source": entry.source,
            "state": entry.state.value,
            "unique_id": entry.unique_id,
            "disabled_by": entry.disabled_by,
            "data": config_data,
            "options": dict(entry.options),
        },
        "coordinator": coordinator_data,
        "coordinator_info": coordinator_info,
        "devices": devices_info,
        "yaml_configs": hass.data.get(DOMAIN, {}).get("yaml_configs", []),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator: EwayDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get entity registry
    entity_registry = er.async_get(hass)

    # Get entities for this device
    entities = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )

    device_entities = []
    for entity in entities:
        entity_info: dict[str, Any] = {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "platform": entity.platform,
            "device_class": entity.device_class,
            "unit_of_measurement": entity.unit_of_measurement,
            "disabled_by": entity.disabled_by,
            "entity_category": entity.entity_category,
            "unique_id": entity.unique_id,
        }

        # Get current state if entity is enabled
        if not entity.disabled_by:
            state = hass.states.get(entity.entity_id)
            if state:
                entity_info["state"] = {
                    "state": state.state,
                    "attributes": dict(state.attributes),
                    "last_changed": state.last_changed.isoformat(),
                    "last_updated": state.last_updated.isoformat(),
                }

        device_entities.append(entity_info)

    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "model": device.model,
            "manufacturer": device.manufacturer,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "identifiers": list(device.identifiers),
            "connections": list(device.connections),
            "via_device_id": device.via_device_id,
            "disabled_by": device.disabled_by,
            "configuration_url": device.configuration_url,
        },
        "entities": device_entities,
        "coordinator_data": coordinator.data if coordinator.data else {},
        "coordinator_info": {
            "device_id": coordinator.device_id,
            "device_sn": coordinator.device_sn,
            "device_model": coordinator.device_model,
            "last_update_success": coordinator.last_update_success,
            "last_update_time": coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time
            else None,
            "client_connected": coordinator.client_connected,
        },
    }
