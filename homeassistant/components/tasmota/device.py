"""Device support for the Tasmota integration."""
import logging

from hatasmota import const as hc
from hatasmota.const import (
    CONF_IP,
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_SW_VERSION,
)
from hatasmota.device_status import TasmotaDeviceStatus, TasmotaDeviceStatusConfig
from hatasmota.discovery import clear_discovery_topic
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    EVENT_DEVICE_REGISTRY_UPDATED,
)

from . import discovery
from .const import CONF_DISCOVERY_PREFIX, DATA_DEVICES, DATA_UNSUB, DOMAIN

DEVICE_ATTRIBUTES = [hc.SENSOR_STATUS_RSSI]

_LOGGER = logging.getLogger(__name__)


async def async_start_device_discovery(hass, entry, tasmota_mqtt):
    """Start Tasmota device discovery."""
    hass.data[DATA_DEVICES] = {}

    device_registry = await hass.helpers.device_registry.async_get_registry()

    async def async_discover_device(device_config, mac, full_config):
        """Discover and add a Tasmota device."""
        await async_setup_device(
            hass, mac, device_config, full_config, entry, tasmota_mqtt, device_registry
        )

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
        hass.data[DATA_DEVICES].pop(event.data["device_id"], None)

    hass.data[DATA_UNSUB].append(
        hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, async_device_removed)
    )

    discovery_prefix = entry.data[CONF_DISCOVERY_PREFIX]
    await discovery.async_start(
        hass, discovery_prefix, entry, tasmota_mqtt, async_discover_device
    )


async def async_stop_device_discovery(hass):
    """Stop Tasmota device discovery."""
    await discovery.async_stop(hass)
    hass.data.pop(DATA_DEVICES)


async def _remove_device(hass, config_entry, mac, tasmota_mqtt, device_registry):
    """Remove device from device registry."""
    device = device_registry.async_get_device(set(), {(CONNECTION_NETWORK_MAC, mac)})

    if device is None:
        return

    _LOGGER.debug("Removing tasmota device %s", mac)
    device_registry.async_remove_device(device.id)
    clear_discovery_topic(mac, config_entry.data[CONF_DISCOVERY_PREFIX], tasmota_mqtt)
    if "device_status" not in hass.data[DATA_DEVICES][device.id]:
        return
    device_status = hass.data[DATA_DEVICES][device.id].pop("device_status")
    await device_status.unsubscribe_topics()


async def _update_device(
    hass, config_entry, device_config, full_config, tasmota_mqtt, device_registry
):
    """Add or update device registry."""
    config_entry_id = config_entry.entry_id
    registry_device_info = {
        "connections": {(CONNECTION_NETWORK_MAC, device_config[CONF_MAC])},
        "manufacturer": device_config[CONF_MANUFACTURER],
        "model": device_config[CONF_MODEL],
        "name": device_config[CONF_NAME],
        "sw_version": device_config[CONF_SW_VERSION],
        "config_entry_id": config_entry_id,
    }
    _LOGGER.debug("Adding or updating tasmota device %s", device_config[CONF_MAC])
    device_entry = device_registry.async_get_or_create(**registry_device_info)
    hass.data[DATA_DEVICES].setdefault(
        device_entry.id, {"mac": device_config[CONF_MAC]}
    )
    device_info = hass.data[DATA_DEVICES][device_entry.id].setdefault("device_info", {})
    device_info.update(
        {
            "ip": device_config[CONF_IP],
            "mac": ":".join(
                device_config[CONF_MAC].lower()[i : i + 2] for i in range(0, 12, 2)
            ),
            "manufacturer": device_config[CONF_MANUFACTURER],
            "model": device_config[CONF_MODEL],
            "name": device_config[CONF_NAME],
            "sw_version": device_config[CONF_SW_VERSION],
        }
    )

    def _device_status_updated(attributes):
        device_info = hass.data[DATA_DEVICES][device_entry.id]["device_info"]
        if hc.SENSOR_STATUS_RSSI in attributes:
            device_info["rssi"] = attributes[hc.SENSOR_STATUS_RSSI]

    device_status_config = TasmotaDeviceStatusConfig.from_discovery_message(full_config)
    if "device_status" not in hass.data[DATA_DEVICES][device_entry.id]:
        device_status = TasmotaDeviceStatus(
            config=device_status_config, mqtt_client=tasmota_mqtt
        )
        device_status.set_on_state_callback(_device_status_updated)
        hass.data[DATA_DEVICES][device_entry.id]["device_status"] = device_status
    else:
        device_status = hass.data[DATA_DEVICES][device_entry.id]["device_status"]
        if device_status.config_same(device_status_config):
            return
        device_status.config_update(device_status_config)
    await device_status.subscribe_topics()


async def async_setup_device(
    hass, mac, device_config, full_config, config_entry, tasmota_mqtt, device_registry
):
    """Set up the Tasmota device."""
    if not device_config:
        await _remove_device(hass, config_entry, mac, tasmota_mqtt, device_registry)
    else:
        await _update_device(
            hass,
            config_entry,
            device_config,
            full_config,
            tasmota_mqtt,
            device_registry,
        )


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


@websocket_api.websocket_command(
    {vol.Required("type"): "tasmota/device", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def websocket_get_device(hass, connection, msg):
    """Get extended device information."""
    device_id = msg["device_id"]
    if device_id not in hass.data[DATA_DEVICES]:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Unknown device"
        )
        return
    device_info = hass.data[DATA_DEVICES][device_id]["device_info"]
    connection.send_message(websocket_api.result_message(msg["id"], device_info))
