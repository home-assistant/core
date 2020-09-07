"""Support for MQTT message handling."""
import logging

import voluptuous as vol

from hatasmota.const import (
    CONF_ID,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_SW_VERSION,
)
from homeassistant.components.mqtt import async_publish, valid_subscribe_topic
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import discovery
from .const import CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX, DOMAIN
from .discovery import TASMOTA_DISCOVERY_DEVICE

# from typing import Optional


_LOGGER = logging.getLogger(__name__)

DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_DISCOVERY_PREFIX, default=DEFAULT_PREFIX
        ): valid_subscribe_topic,
    }
)

DEVICE_IDS = "tasmota_devices"


async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the Tasmota component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Tasmota from a config entry."""
    conf = DOMAIN_SCHEMA(dict(entry.data))
    hass.data[DEVICE_IDS] = {}

    await discovery.async_start(hass, conf[CONF_DISCOVERY_PREFIX], entry)

    async def async_device_removed(event):
        """Handle the removal of a device."""
        if event.data["action"] != "remove":
            return
        serial_number = hass.data[DEVICE_IDS][event.data["device_id"]]
        discovery_topic = f"{conf[CONF_DISCOVERY_PREFIX]}/{serial_number}/config"
        async_publish(
            hass,
            discovery_topic,
            "",
            retain=True,
        )

    async def async_discover_device(config, discovery_hash, discovery_payload):
        """Discover and add a Tasmota device."""
        await async_setup_device(hass, discovery_hash, config, entry)

    async_dispatcher_connect(hass, TASMOTA_DISCOVERY_DEVICE, async_discover_device)
    hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)

    return True


async def _remove_device(hass, discovery_hash):
    """Remove device from device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device({(DOMAIN, discovery_hash)}, None)

    if device is None:
        return

    _LOGGER.info("Removing tasmota device %s", discovery_hash)
    device_registry.async_remove_device(device.id)


async def _update_device(hass, config_entry, config):
    """Add or update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = {"identifiers": {(DOMAIN, config[CONF_ID])}}
    device_info["manufacturer"] = config[CONF_MANUFACTURER]
    device_info["model"] = config[CONF_MODEL]
    device_info["name"] = config[CONF_NAME]
    device_info["sw_version"] = config[CONF_SW_VERSION]

    device_info["config_entry_id"] = config_entry_id
    _LOGGER.info("Adding or updating tasmota device %s", config[CONF_ID])
    device = device_registry.async_get_or_create(**device_info)
    hass.data[DEVICE_IDS][device.id] = config[CONF_ID]


async def async_setup_device(hass, discovery_hash, config, config_entry):
    """Set up the Tasmota device."""
    if not config:
        await _remove_device(hass, discovery_hash)
    else:
        await _update_device(hass, config_entry, config)
