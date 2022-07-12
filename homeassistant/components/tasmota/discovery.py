"""Support for Tasmota device discovery."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging

from hatasmota.discovery import (
    TasmotaDiscovery,
    get_device_config as tasmota_get_device_config,
    get_entities_for_platform as tasmota_get_entities_for_platform,
    get_entity as tasmota_get_entity,
    get_trigger as tasmota_get_trigger,
    get_triggers as tasmota_get_triggers,
    unique_id_from_hash,
)
from hatasmota.entity import TasmotaEntityConfig
from hatasmota.models import DiscoveryHashType, TasmotaDeviceConfig
from hatasmota.mqtt import TasmotaMQTTClient
from hatasmota.sensor import TasmotaBaseSensorConfig

from homeassistant.components import sensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_entries_for_device

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

ALREADY_DISCOVERED = "tasmota_discovered_components"
TASMOTA_DISCOVERY_ENTITY_NEW = "tasmota_discovery_entity_new_{}"
TASMOTA_DISCOVERY_ENTITY_UPDATED = "tasmota_discovery_entity_updated_{}_{}_{}_{}"
TASMOTA_DISCOVERY_INSTANCE = "tasmota_discovery_instance"

SetupDeviceCallback = Callable[[TasmotaDeviceConfig, str], Awaitable[None]]


def clear_discovery_hash(
    hass: HomeAssistant, discovery_hash: DiscoveryHashType
) -> None:
    """Clear entry in ALREADY_DISCOVERED list."""
    if ALREADY_DISCOVERED not in hass.data:
        # Discovery is shutting down
        return
    del hass.data[ALREADY_DISCOVERED][discovery_hash]


def set_discovery_hash(hass: HomeAssistant, discovery_hash: DiscoveryHashType) -> None:
    """Set entry in ALREADY_DISCOVERED list."""
    hass.data[ALREADY_DISCOVERED][discovery_hash] = {}


async def async_start(
    hass: HomeAssistant,
    discovery_topic: str,
    config_entry: ConfigEntry,
    tasmota_mqtt: TasmotaMQTTClient,
    setup_device: SetupDeviceCallback,
) -> None:
    """Start Tasmota device discovery."""

    def _discover_entity(
        tasmota_entity_config: TasmotaEntityConfig | None,
        discovery_hash: DiscoveryHashType,
        platform: str,
    ) -> None:
        """Handle adding or updating a discovered entity."""
        if not tasmota_entity_config:
            # Entity disabled, clean up entity registry
            entity_registry = er.async_get(hass)
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
            tasmota_entity = tasmota_get_entity(tasmota_entity_config, tasmota_mqtt)
            if not tasmota_entity:
                _LOGGER.error("Failed to create entity %s %s", platform, discovery_hash)
                return

            _LOGGER.debug(
                "Adding new entity: %s %s %s",
                platform,
                discovery_hash,
                tasmota_entity.unique_id,
            )

            hass.data[ALREADY_DISCOVERED][discovery_hash] = None

            async_dispatcher_send(
                hass,
                TASMOTA_DISCOVERY_ENTITY_NEW.format(platform),
                tasmota_entity,
                discovery_hash,
            )

    async def async_device_discovered(payload: dict, mac: str) -> None:
        """Process the received message."""

        if ALREADY_DISCOVERED not in hass.data:
            # Discovery is shutting down
            return

        _LOGGER.debug("Received discovery data for tasmota device: %s", mac)
        tasmota_device_config = tasmota_get_device_config(payload)
        await setup_device(tasmota_device_config, mac)

        if not payload:
            return

        tasmota_triggers = tasmota_get_triggers(payload)
        for trigger_config in tasmota_triggers:
            discovery_hash: DiscoveryHashType = (
                mac,
                "automation",
                "trigger",
                trigger_config.trigger_id,
            )
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

        for platform in PLATFORMS:
            tasmota_entities = tasmota_get_entities_for_platform(payload, platform)
            for (tasmota_entity_config, discovery_hash) in tasmota_entities:
                _discover_entity(tasmota_entity_config, discovery_hash, platform)

    async def async_sensors_discovered(
        sensors: list[tuple[TasmotaBaseSensorConfig, DiscoveryHashType]], mac: str
    ) -> None:
        """Handle discovery of (additional) sensors."""
        platform = sensor.DOMAIN

        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        device = device_registry.async_get_device(
            set(), {(dr.CONNECTION_NETWORK_MAC, mac)}
        )

        if device is None:
            _LOGGER.warning("Got sensors for unknown device mac: %s", mac)
            return

        orphaned_entities = {
            entry.unique_id
            for entry in async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            )
            if entry.domain == sensor.DOMAIN and entry.platform == DOMAIN
        }
        for (tasmota_sensor_config, discovery_hash) in sensors:
            if tasmota_sensor_config:
                orphaned_entities.discard(tasmota_sensor_config.unique_id)
            _discover_entity(tasmota_sensor_config, discovery_hash, platform)
        for unique_id in orphaned_entities:
            entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id:
                _LOGGER.debug("Removing entity: %s %s", platform, entity_id)
                entity_registry.async_remove(entity_id)

    hass.data[ALREADY_DISCOVERED] = {}

    tasmota_discovery = TasmotaDiscovery(discovery_topic, tasmota_mqtt)
    await tasmota_discovery.start_discovery(
        async_device_discovered, async_sensors_discovered
    )
    hass.data[TASMOTA_DISCOVERY_INSTANCE] = tasmota_discovery


async def async_stop(hass: HomeAssistant) -> None:
    """Stop Tasmota device discovery."""
    hass.data.pop(ALREADY_DISCOVERED)
    tasmota_discovery = hass.data.pop(TASMOTA_DISCOVERY_INSTANCE)
    await tasmota_discovery.stop_discovery()
