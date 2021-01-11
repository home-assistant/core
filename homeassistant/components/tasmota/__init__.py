"""The Tasmota integration."""
import asyncio
import logging

from hatasmota.const import (
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_SW_VERSION,
)
from hatasmota.discovery import clear_discovery_topic
from hatasmota.mqtt import TasmotaMQTTClient
import voluptuous as vol

from homeassistant.components import mqtt, websocket_api
from homeassistant.components.mqtt.subscription import (
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    EVENT_DEVICE_REGISTRY_UPDATED,
    async_entries_for_config_entry,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import device_automation, discovery
from .const import (
    CONF_DISCOVERY_PREFIX,
    DATA_REMOVE_DISCOVER_COMPONENT,
    DATA_UNSUB,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the Tasmota component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Tasmota from a config entry."""
    websocket_api.async_register_command(hass, websocket_remove_device)
    hass.data[DATA_UNSUB] = []

    def _publish(*args, **kwds):
        mqtt.async_publish(hass, *args, **kwds)

    async def _subscribe_topics(sub_state, topics):
        # Optionally mark message handlers as callback
        for topic in topics.values():
            if "msg_callback" in topic and "event_loop_safe" in topic:
                topic["msg_callback"] = callback(topic["msg_callback"])
        return await async_subscribe_topics(hass, sub_state, topics)

    async def _unsubscribe_topics(sub_state):
        return await async_unsubscribe_topics(hass, sub_state)

    tasmota_mqtt = TasmotaMQTTClient(_publish, _subscribe_topics, _unsubscribe_topics)

    device_registry = await hass.helpers.device_registry.async_get_registry()

    def async_discover_device(config, mac):
        """Discover and add a Tasmota device."""
        async_setup_device(hass, mac, config, entry, tasmota_mqtt, device_registry)

    async def async_device_removed(event):
        """Handle the removal of a device."""
        device_registry = await hass.helpers.device_registry.async_get_registry()
        if event.data["action"] != "remove":
            return

        device = device_registry.deleted_devices[event.data["device_id"]]

        if entry.entry_id not in device.config_entries:
            return

        macs = [c[1] for c in device.connections if c[0] == CONNECTION_NETWORK_MAC]
        for mac in macs:
            clear_discovery_topic(mac, entry.data[CONF_DISCOVERY_PREFIX], tasmota_mqtt)

    hass.data[DATA_UNSUB].append(
        hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)
    )

    async def start_platforms():
        await device_automation.async_setup_entry(hass, entry)
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, component)
                for component in PLATFORMS
            ]
        )

        discovery_prefix = entry.data[CONF_DISCOVERY_PREFIX]
        await discovery.async_start(
            hass, discovery_prefix, entry, tasmota_mqtt, async_discover_device
        )

    hass.async_create_task(start_platforms())
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    # cleanup platforms
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    # disable discovery
    await discovery.async_stop(hass)

    # cleanup subscriptions
    for unsub in hass.data[DATA_UNSUB]:
        unsub()
    hass.data.pop(DATA_REMOVE_DISCOVER_COMPONENT.format("device_automation"))()
    for component in PLATFORMS:
        hass.data.pop(DATA_REMOVE_DISCOVER_COMPONENT.format(component))()

    # deattach device triggers
    device_registry = await hass.helpers.device_registry.async_get_registry()
    devices = async_entries_for_config_entry(device_registry, entry.entry_id)
    for device in devices:
        await device_automation.async_remove_automations(hass, device.id)

    return True


def _remove_device(hass, config_entry, mac, tasmota_mqtt, device_registry):
    """Remove device from device registry."""
    device = device_registry.async_get_device(set(), {(CONNECTION_NETWORK_MAC, mac)})

    if device is None:
        return

    _LOGGER.debug("Removing tasmota device %s", mac)
    device_registry.async_remove_device(device.id)
    clear_discovery_topic(mac, config_entry.data[CONF_DISCOVERY_PREFIX], tasmota_mqtt)


def _update_device(hass, config_entry, config, device_registry):
    """Add or update device registry."""
    config_entry_id = config_entry.entry_id
    device_info = {
        "connections": {(CONNECTION_NETWORK_MAC, config[CONF_MAC])},
        "manufacturer": config[CONF_MANUFACTURER],
        "model": config[CONF_MODEL],
        "name": config[CONF_NAME],
        "sw_version": config[CONF_SW_VERSION],
        "config_entry_id": config_entry_id,
    }
    _LOGGER.debug("Adding or updating tasmota device %s", config[CONF_MAC])
    device_registry.async_get_or_create(**device_info)


def async_setup_device(hass, mac, config, config_entry, tasmota_mqtt, device_registry):
    """Set up the Tasmota device."""
    if not config:
        _remove_device(hass, config_entry, mac, tasmota_mqtt, device_registry)
    else:
        _update_device(hass, config_entry, config, device_registry)


@websocket_api.websocket_command(
    {vol.Required("type"): "tasmota/device/remove", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def websocket_remove_device(hass, connection, msg):
    """Delete device."""
    device_id = msg["device_id"]
    dev_registry = await hass.helpers.device_registry.async_get_registry()

    device = dev_registry.async_get(device_id)
    if not device:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Device not found"
        )
        return

    for config_entry in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry)
        # Only delete the device if it belongs to a Tasmota device entry
        if config_entry.domain == DOMAIN:
            dev_registry.async_remove_device(device_id)
            connection.send_message(websocket_api.result_message(msg["id"]))
            return

    connection.send_error(
        msg["id"], websocket_api.const.ERR_NOT_FOUND, "Non Tasmota device"
    )
