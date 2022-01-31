"""Diagnostics support for UniFi Network."""
from __future__ import annotations

from collections.abc import Mapping
from itertools import chain
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_CONTROLLER, DOMAIN as UNIFI_DOMAIN

TO_REDACT = {CONF_CONTROLLER, CONF_PASSWORD}
REDACT_CONFIG = {CONF_CONTROLLER, CONF_PASSWORD, CONF_USERNAME}
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
REDACT_WLANS = {"bc_filter_list", "x_passphrase"}


@callback
def async_replace_data(data: Mapping, to_replace: dict[str, str]) -> dict[str, Any]:
    """Replace sensitive data in a dict."""
    if not isinstance(data, (Mapping, list, set, tuple)):
        return to_replace.get(data, data)

    redacted = {**data}

    for key, value in redacted.items():
        if isinstance(value, dict):
            redacted[key] = async_replace_data(value, to_replace)
        elif isinstance(value, (list, set, tuple)):
            redacted[key] = [async_replace_data(item, to_replace) for item in value]
        elif isinstance(value, str):
            if value in to_replace:
                redacted[key] = to_replace[value]
            elif value.count(":") == 5:
                redacted[key] = REDACTED

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {}
    macs_to_redact: dict[str, str] = {}

    counter = 0
    for mac in chain(controller.api.clients, controller.api.devices):
        macs_to_redact[mac] = format_mac(str(counter).zfill(12))
        counter += 1

    for device in controller.api.devices.values():
        for entry in device.raw.get("ethernet_table", []):
            mac = entry.get("mac", "")
            if mac not in macs_to_redact:
                macs_to_redact[mac] = format_mac(str(counter).zfill(12))
                counter += 1

    diag["config"] = async_redact_data(
        async_replace_data(config_entry.as_dict(), macs_to_redact), REDACT_CONFIG
    )
    diag["site_role"] = controller.site_role
    diag["entities"] = async_replace_data(controller.entities, macs_to_redact)
    diag["clients"] = {
        macs_to_redact[k]: async_redact_data(
            async_replace_data(v.raw, macs_to_redact), REDACT_CLIENTS
        )
        for k, v in controller.api.clients.items()
    }
    diag["devices"] = {
        macs_to_redact[k]: async_redact_data(
            async_replace_data(v.raw, macs_to_redact), REDACT_DEVICES
        )
        for k, v in controller.api.devices.items()
    }
    diag["dpi_apps"] = {k: v.raw for k, v in controller.api.dpi_apps.items()}
    diag["dpi_groups"] = {k: v.raw for k, v in controller.api.dpi_groups.items()}
    diag["wlans"] = {
        k: async_redact_data(async_replace_data(v.raw, macs_to_redact), REDACT_WLANS)
        for k, v in controller.api.wlans.items()
    }

    return diag
