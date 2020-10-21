"""Support for Tasmota device discovery."""
import asyncio
import logging

from hatasmota.discovery import (
    TasmotaDiscovery,
    get_device_config as tasmota_get_device_config,
    get_entities_for_platform as tasmota_get_entities_for_platform,
    get_entity as tasmota_get_entity,
    get_trigger as tasmota_get_trigger,
    get_triggers as tasmota_get_triggers,
    has_entities_with_platform as tasmota_has_entities_with_platform,
    unique_id_from_hash,
)

import homeassistant.components.sensor as sensor
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = [
    "binary_sensor",
    "light",
    "sensor",
    "switch",
]

ALREADY_DISCOVERED = "tasmota_discovered_components"
CONFIG_ENTRY_IS_SETUP = "tasmota_config_entry_is_setup"
DATA_CONFIG_ENTRY_LOCK = "tasmota_config_entry_lock"
TASMOTA_DISCOVERY_DEVICE = "tasmota_discovery_device"
TASMOTA_DISCOVERY_ENTITY_NEW = "tasmota_discovery_entity_new_{}"
TASMOTA_DISCOVERY_ENTITY_UPDATED = "tasmota_discovery_entity_updated_{}_{}_{}_{}"


def clear_discovery_hash(hass, discovery_hash):
    """Clear entry in ALREADY_DISCOVERED list."""
    del hass.data[ALREADY_DISCOVERED][discovery_hash]


def set_discovery_hash(hass, discovery_hash):
    """Set entry in ALREADY_DISCOVERED list."""
    hass.data[ALREADY_DISCOVERED][discovery_hash] = {}


async def async_start(
    hass: HomeAssistantType, discovery_topic, config_entry, tasmota_mqtt
) -> bool:
    """Start Tasmota device discovery."""

    async def _load_platform(platform):
        """Load a Tasmota platform if not already done."""
        async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
            config_entries_key = f"{platform}.tasmota"
            if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                await hass.config_entries.async_forward_entry_setup(
                    config_entry, platform
                )
                hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

    async def _discover_entity(tasmota_entity_config, discovery_hash, platform):
        """Handle adding or updating a discovered entity."""
        if not tasmota_entity_config:
            # Entity disabled, clean up entity registry
            entity_registry = await hass.helpers.entity_registry.async_get_registry()
            unique_id = unique_id_from_hash(discovery_hash)
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id:
                _LOGGER.debug("Removing entity: %s %s", platform, discovery_hash)
                entity_registry.async_remove(entity_id)
            return

        if discovery_hash in hass.data[ALREADY_DISCOVERED]:
            _LOGGER.debug(
                "Entity already added, sending update: %s %s",
                platform,
                discovery_hash,
            )
            async_dispatcher_send(
                hass,
                TASMOTA_DISCOVERY_ENTITY_UPDATED.format(*discovery_hash),
                tasmota_entity_config,
            )
        else:
            _LOGGER.debug("Adding new entity: %s %s", platform, discovery_hash)
            tasmota_entity = tasmota_get_entity(tasmota_entity_config, tasmota_mqtt)

            hass.data[ALREADY_DISCOVERED][discovery_hash] = None

            async_dispatcher_send(
                hass,
                TASMOTA_DISCOVERY_ENTITY_NEW.format(platform),
                tasmota_entity,
                discovery_hash,
            )

    async def async_device_discovered(payload, mac):
        """Process the received message."""

        if ALREADY_DISCOVERED not in hass.data:
            hass.data[ALREADY_DISCOVERED] = {}

        _LOGGER.debug("Received discovery data for tasmota device: %s", mac)
        tasmota_device_config = tasmota_get_device_config(payload)
        async_dispatcher_send(
            hass, TASMOTA_DISCOVERY_DEVICE, tasmota_device_config, mac
        )

        if not payload:
            return

        tasmota_triggers = tasmota_get_triggers(payload)
        async with hass.data[DATA_CONFIG_ENTRY_LOCK]:
            if any(trigger.is_active for trigger in tasmota_triggers):
                config_entries_key = "device_automation.tasmota"
                if config_entries_key not in hass.data[CONFIG_ENTRY_IS_SETUP]:
                    # Local import to avoid circular dependencies
                    # pylint: disable=import-outside-toplevel
                    from . import device_automation

                    await device_automation.async_setup_entry(hass, config_entry)
                    hass.data[CONFIG_ENTRY_IS_SETUP].add(config_entries_key)

        for trigger_config in tasmota_triggers:
            discovery_hash = (mac, "automation", "trigger", trigger_config.trigger_id)
            if discovery_hash in hass.data[ALREADY_DISCOVERED]:
                _LOGGER.debug(
                    "Trigger already added, sending update: %s",
                    discovery_hash,
                )
                async_dispatcher_send(
                    hass,
                    TASMOTA_DISCOVERY_ENTITY_UPDATED.format(*discovery_hash),
                    trigger_config,
                )
            elif trigger_config.is_active:
                _LOGGER.debug("Adding new trigger: %s", discovery_hash)
                hass.data[ALREADY_DISCOVERED][discovery_hash] = None

                tasmota_trigger = tasmota_get_trigger(trigger_config, tasmota_mqtt)

                async_dispatcher_send(
                    hass,
                    TASMOTA_DISCOVERY_ENTITY_NEW.format("device_automation"),
                    tasmota_trigger,
                    discovery_hash,
                )

        for platform in SUPPORTED_PLATFORMS:
            if not tasmota_has_entities_with_platform(payload, platform):
                continue
            await _load_platform(platform)

        for platform in SUPPORTED_PLATFORMS:
            tasmota_entities = tasmota_get_entities_for_platform(payload, platform)
            for (tasmota_entity_config, discovery_hash) in tasmota_entities:
                await _discover_entity(tasmota_entity_config, discovery_hash, platform)

    async def async_sensors_discovered(sensors, mac):
        """Handle discovery of (additional) sensors."""
        platform = sensor.DOMAIN
        await _load_platform(platform)

        device_registry = await hass.helpers.device_registry.async_get_registry()
        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        device = device_registry.async_get_device(set(), {("mac", mac)})

        if device is None:
            _LOGGER.warning("Got sensors for unknown device mac: %s", mac)
            return

        orphaned_entities = {
            entry.unique_id
            for entry in async_entries_for_device(entity_registry, device.id)
            if entry.domain == sensor.DOMAIN and entry.platform == DOMAIN
        }
        for (tasmota_sensor_config, discovery_hash) in sensors:
            if tasmota_sensor_config:
                orphaned_entities.discard(tasmota_sensor_config.unique_id)
            await _discover_entity(tasmota_sensor_config, discovery_hash, platform)
        for unique_id in orphaned_entities:
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id:
                _LOGGER.debug("Removing entity: %s %s", platform, entity_id)
                entity_registry.async_remove(entity_id)

    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    tasmota_discovery = TasmotaDiscovery(discovery_topic, tasmota_mqtt)
    await tasmota_discovery.start_discovery(
        async_device_discovered, async_sensors_discovered
    )
