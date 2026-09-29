"""ESPHome websocket API."""

from typing import Any, cast

import probatio

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

ZWAVE_JS_DOMAIN = "zwave_js"

_UNAVAILABLE_CAPABILITIES: dict[str, Any] = {
    "bluetooth_proxy": {"supported": False},
    "zwave_proxy": {"supported": False, "home_id": 0, "config_entry_id": None},
    "serial_proxies": [],
}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, get_encryption_key)
    websocket_api.async_register_command(hass, get_device_capabilities)


def _is_main_esphome_device(device: dr.DeviceEntry) -> bool:
    """Return True if device is the MAC-connected ESPHome node."""
    return any(
        conn_type == dr.CONNECTION_NETWORK_MAC for conn_type, _ in device.connections
    )


def _zwave_js_config_entry_id(hass: HomeAssistant, home_id: int) -> str | None:
    """Return the entry ID of the zwave_js entry whose unique ID is this home ID."""
    if not home_id:
        return None
    home_id_str = str(home_id)
    # Ignored and disabled entries are not the configured network. Scan all
    # matches because the unique ID index returns only the first one, and
    # compare with str() so legacy integer unique IDs still match.
    for entry in hass.config_entries.async_entries(
        ZWAVE_JS_DOMAIN,
        include_ignore=False,
        include_disabled=False,
    ):
        if str(entry.unique_id) == home_id_str:
            return entry.entry_id
    return None


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "esphome/get_encryption_key",
        probatio.Required(ENTRY_ID): str,
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
        probatio.Required(TYPE): "esphome/get_device_capabilities",
        probatio.Required(DEVICE_ID): str,
    }
)
def get_device_capabilities(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return cached ESPHome DeviceInfo capabilities for the device page."""
    device, candidate = dr.async_get_device_and_config_entry_for_domain(
        hass, msg[DEVICE_ID], domain=DOMAIN, include_child_devices=False
    )
    if device is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Device not found"
        )
        return

    if candidate is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not an ESPHome device",
        )
        return
    entry = cast(ESPHomeConfigEntry, candidate)

    if not _is_main_esphome_device(device):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not the main ESPHome device",
        )
        return

    device_info = None
    if entry.state is ConfigEntryState.LOADED:
        device_info = entry.runtime_data.device_info

    if device_info is None:
        connection.send_result(msg["id"], _UNAVAILABLE_CAPABILITIES)
        return

    entry_data = entry.runtime_data
    home_id = device_info.zwave_home_id or 0
    connection.send_result(
        msg["id"],
        {
            "bluetooth_proxy": {
                "supported": bool(
                    device_info.bluetooth_proxy_feature_flags_compat(
                        entry_data.api_version
                    )
                ),
            },
            "zwave_proxy": {
                "supported": bool(device_info.zwave_proxy_feature_flags),
                "home_id": home_id,
                "config_entry_id": _zwave_js_config_entry_id(hass, home_id),
            },
            "serial_proxies": [
                {
                    "name": proxy.name,
                    "port_type": (
                        proxy.port_type.name if proxy.port_type is not None else None
                    ),
                    "url": str(build_url(entry.entry_id, proxy.name)),
                }
                for proxy in device_info.serial_proxies
            ],
        },
    )
