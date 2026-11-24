"""Diagnostics support for UniFi Network."""

from collections.abc import Mapping
from itertools import chain
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac

from . import UnifiConfigEntry

TO_REDACT = {CONF_PASSWORD}
REDACT_CONFIG = {CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME}
REDACT_CLIENTS = {"bssid", "essid"}
REDACT_DEVICES = {
    "anon_id",
    "gateway_mac",
    "geo_info",
    "serial",
    "x_authkey",
    "x_fingerprint",
    "x_iapp_key",
    "x_ssh_hostkey_fingerprint",
    "x_vwirekey",
}
REDACT_WLANS = {"bc_filter_list", "password", "x_passphrase"}


@callback
def async_replace_dict_data(
    data: Mapping, to_replace: dict[str, str]
) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}
    for key, value in data.items():
        if isinstance(value, dict):
            redacted[key] = async_replace_dict_data(value, to_replace)
        elif isinstance(value, (list, set, tuple)):
            redacted[key] = async_replace_list_data(value, to_replace)
        elif isinstance(value, str):
            if value in to_replace:
                redacted[key] = to_replace[value]
            elif value.count(":") == 5:
                redacted[key] = REDACTED
    return redacted


@callback
def async_replace_list_data(
    data: list | set | tuple, to_replace: dict[str, str]
) -> list[Any]:
    """Redact sensitive data in a list."""
    redacted = []
    for item in data:
        new_value: Any | None = None
        if isinstance(item, (list, set, tuple)):
            new_value = async_replace_list_data(item, to_replace)
        elif isinstance(item, Mapping):
            new_value = async_replace_dict_data(item, to_replace)
        elif isinstance(item, str):
            if item in to_replace:
                new_value = to_replace[item]
            elif item.count(":") == 5:
                new_value = REDACTED
        redacted.append(new_value or item)
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UnifiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = config_entry.runtime_data
    if hub.config.api_key_only:
        return _async_network_api_diagnostics(config_entry)
    diag: dict[str, Any] = {}
    macs_to_redact: dict[str, str] = {}

    counter = 0
    for mac in chain(hub.api.clients, hub.api.devices):
        macs_to_redact[mac] = format_mac(str(counter).zfill(12))
        counter += 1

    for device in hub.api.devices.values():
        for entry in device.raw.get("ethernet_table", []):
            mac = entry.get("mac", "")
            if mac not in macs_to_redact:
                macs_to_redact[mac] = format_mac(str(counter).zfill(12))
                counter += 1

    diag["config"] = async_redact_data(
        async_replace_dict_data(config_entry.as_dict(), macs_to_redact), REDACT_CONFIG
    )
    diag["role_is_admin"] = hub.is_admin
    diag["clients"] = {
        macs_to_redact[k]: async_redact_data(
            async_replace_dict_data(v.raw, macs_to_redact), REDACT_CLIENTS
        )
        for k, v in hub.api.clients.items()
    }
    diag["devices"] = {
        macs_to_redact[k]: async_redact_data(
            async_replace_dict_data(v.raw, macs_to_redact), REDACT_DEVICES
        )
        for k, v in hub.api.devices.items()
    }
    diag["dpi_apps"] = {k: v.raw for k, v in hub.api.dpi_apps.items()}
    diag["dpi_groups"] = {k: v.raw for k, v in hub.api.dpi_groups.items()}
    diag["wlans"] = {
        k: async_redact_data(
            async_replace_dict_data(v.raw, macs_to_redact), REDACT_WLANS
        )
        for k, v in hub.api.wlans.items()
    }

    return diag


@callback
def _async_network_api_diagnostics(config_entry: UnifiConfigEntry) -> dict[str, Any]:
    """Return diagnostics of an entry using the Integration API."""
    hub = config_entry.runtime_data
    network = hub.api.network
    macs_to_redact = {
        mac: format_mac(str(counter).zfill(12))
        for counter, mac in enumerate(chain(network.clients, network.devices))
    }

    return {
        "config": async_redact_data(
            async_replace_dict_data(config_entry.as_dict(), macs_to_redact),
            REDACT_CONFIG,
        ),
        "network_version": hub.network_version,
        "clients": {
            macs_to_redact[mac]: async_replace_dict_data(client.raw, macs_to_redact)
            for mac, client in network.clients.items()
        },
        "devices": {
            macs_to_redact[mac]: async_replace_dict_data(device.raw, macs_to_redact)
            for mac, device in network.devices.items()
        },
        "ports": {
            f"{macs_to_redact[obj_id.partition('_')[0]]}_{port.idx}": (
                async_replace_dict_data(port.raw, macs_to_redact)
            )
            for obj_id, port in hub.network_ports.items()
        },
        "statistics": {
            macs_to_redact[mac]: async_replace_dict_data(statistics.raw, macs_to_redact)
            for mac, statistics in hub.network_statistics.items()
        },
    }
