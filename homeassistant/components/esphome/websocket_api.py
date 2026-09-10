"""ESPHome websocket API."""

from typing import Any, cast

from aioesphomeapi.model import SerialProxyPortType
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_NOISE_PSK, DOMAIN
from .entry_data import ESPHomeConfigEntry
from .serial_proxy import build_url

TYPE = "type"
ENTRY_ID = "entry_id"
DEVICE_ID = "device_id"

_UNAVAILABLE_CAPABILITIES: dict[str, Any] = {
    "available": False,
    "bluetooth_proxy": {"supported": False},
    "zwave_proxy": {"supported": False, "home_id": 0},
    "serial_proxies": [],
}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, get_encryption_key)
    websocket_api.async_register_command(hass, get_device_capabilities)


def _is_main_esphome_device(device: dr.DeviceEntry, mac_address: str | None) -> bool:
    """Return True if device is the MAC-connected ESPHome node."""
    if mac_address is None:
        return any(
            conn_type == dr.CONNECTION_NETWORK_MAC
            for conn_type, _ in device.connections
        )
    return (
        dr.CONNECTION_NETWORK_MAC,
        dr.format_mac(mac_address),
    ) in device.connections


def _serial_port_type_name(port_type: SerialProxyPortType | int | None) -> str | None:
    """Return the SerialProxyPortType name, or None if unknown."""
    if port_type is None:
        return None
    try:
        return SerialProxyPortType(port_type).name
    except ValueError:
        return None


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "esphome/get_encryption_key",
        vol.Required(ENTRY_ID): str,
    }
)
def get_encryption_key(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the encryption key for an ESPHome config entry."""
    entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Config entry not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "encryption_key": entry.data.get(CONF_NOISE_PSK),
        },
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "esphome/get_device_capabilities",
        vol.Required(DEVICE_ID): str,
    }
)
def get_device_capabilities(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return cached ESPHome DeviceInfo capabilities for the device page."""
    device = dr.async_get(hass).async_get(msg[DEVICE_ID])
    if device is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Device not found"
        )
        return

    entry: ESPHomeConfigEntry | None = None
    for entry_id in device.config_entries:
        candidate = hass.config_entries.async_get_entry(entry_id)
        if candidate is not None and candidate.domain == DOMAIN:
            entry = cast(ESPHomeConfigEntry, candidate)
            break

    if entry is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not an ESPHome device",
        )
        return

    # Sub-devices share the config entry but not node-level proxy capabilities.
    if not isinstance(device, dr.DeviceEntry):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not the main ESPHome device",
        )
        return

    device_info = None
    if entry.state is ConfigEntryState.LOADED:
        device_info = entry.runtime_data.device_info

    mac_address = device_info.mac_address if device_info is not None else None
    if not _is_main_esphome_device(device, mac_address):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not the main ESPHome device",
        )
        return

    if device_info is None:
        connection.send_result(msg["id"], _UNAVAILABLE_CAPABILITIES)
        return

    entry_data = entry.runtime_data
    connection.send_result(
        msg["id"],
        {
            "available": entry_data.available,
            "bluetooth_proxy": {
                "supported": bool(
                    device_info.bluetooth_proxy_feature_flags_compat(
                        entry_data.api_version
                    )
                ),
            },
            "zwave_proxy": {
                "supported": bool(device_info.zwave_proxy_feature_flags),
                "home_id": device_info.zwave_home_id or 0,
            },
            "serial_proxies": [
                {
                    "name": proxy.name,
                    "port_type": _serial_port_type_name(proxy.port_type),
                    "url": str(build_url(entry.entry_id, proxy.name)),
                }
                for proxy in device_info.serial_proxies
            ],
        },
    )
