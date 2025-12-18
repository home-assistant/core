"""Lytiva integration using Home Assistant MQTT."""
from __future__ import annotations

import json
import logging

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up Lytiva from a config entry."""
    _LOGGER.info("DEBUG: Lytiva async_setup_entry started! Entry ID: %s", entry.entry_id)

    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")

    hass.data.setdefault(DOMAIN, {})
    
    # 1. Publish Online Status
    _LOGGER.info("Publishing online status to LYT/homeassistant/status")
    try:
        await mqtt.async_publish(hass, "LYT/homeassistant/status", "online", qos=1, retain=True)
    except Exception as e:
        _LOGGER.exception("Failed to publish status: %s", e)

    # 2. Subscribe to Discovery Topics
    # Pattern: LYT/homeassistant/<platform>/<device_id>/config
    async def async_discovery_message_received(msg):
        """Handle discovery MQTT message."""
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            _LOGGER.warning("Invalid JSON in discovery: %s", msg.payload)
            return

        topic_parts = msg.topic.split("/")
        # topic: LYT/homeassistant/light/123/config
        if len(topic_parts) < 5:
            return

        platform = topic_parts[2]
        device_id = topic_parts[3]

        # -------------------------------------------------------------------------
        #  HANDLE REMOVAL (Empty Payload)
        # -------------------------------------------------------------------------
        if not payload:
            _LOGGER.info("Removing entity %s (platform %s) due to empty discovery payload", device_id, platform)
            
            from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
            from homeassistant.helpers.device_registry import async_get as async_get_device_registry

            entity_registry = async_get_entity_registry(hass)
            device_registry = async_get_device_registry(hass)

            # 1. Find and remove entity
            entity_entry = None
            for entity in list(entity_registry.entities.values()):
                # Match strict unique_id or address-based naming
                if (entity.unique_id == device_id or 
                    entity.unique_id == str(device_id) or
                    entity.unique_id.endswith(f"_{device_id}")):
                    
                    if entity.platform == DOMAIN:
                        entity_entry = entity
                        entity_registry.async_remove(entity.entity_id)
                        _LOGGER.debug("Removed entity registry entry: %s", entity.entity_id)
                        break
            
            # 2. If entity found, check if device can be cleaned up
            if entity_entry and entity_entry.device_id:
                # Check if other entities still use this device
                device_entities = [
                    e for e in entity_registry.entities.values() 
                    if e.device_id == entity_entry.device_id
                ]
                
                # If no entities left for this device, remove it
                if not device_entities:
                    try:
                        device_registry.async_remove_device(entity_entry.device_id)
                        _LOGGER.info("Removed device registry entry: %s", entity_entry.device_id)
                    except Exception as e:
                        _LOGGER.error("Failed to remove device: %s", e)
            return

        # -------------------------------------------------------------------------
        #  HANDLE DISCOVERY (Add/Update)
        # -------------------------------------------------------------------------
        # Use 'address' from payload or ID from topic
        if "address" not in payload:
            payload["address"] = device_id
        
        if payload.get("unique_id") is None:
            payload["unique_id"] = device_id

        # Dispatch to platform (e.g., light)
        signal = f"{DOMAIN}_discovery_{platform}"
        async_dispatcher_send(hass, signal, payload)

    # Subscribe to discovery wildcard
    await mqtt.async_subscribe(hass, "LYT/homeassistant/+/+/config", async_discovery_message_received)

    # 3. Setup Light Platform (so it starts listening to dispatcher)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload Lytiva config entry."""
    # Publish Offline
    await mqtt.async_publish(hass, "LYT/homeassistant/status", "offline", retain=True)
    
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
