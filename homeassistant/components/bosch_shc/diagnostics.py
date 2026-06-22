"""Diagnostics support for the Bosch SHC integration.

Returns a redacted JSON snapshot of the controller + every device's raw service
state when the user clicks "Download diagnostics" in
Settings -> Devices & Services. This is the rawscan-equivalent that makes
device/state bug reports (e.g. a cover reporting the wrong direction) actionable
without asking the reporter to run anything by hand.

Credentials (client certificate/key, controller password, OAuth token) and
network identifiers (host/IP, MAC, serials) are redacted via
homeassistant.components.diagnostics.async_redact_data, which walks the structure
recursively and replaces matching keys.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOSTNAME,
    CONF_SHC_CERT,
    CONF_SHC_KEY,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DATA_SESSION,
    DOMAIN,
)

_MANIFEST: dict[str, Any] = json.loads(
    (pathlib.Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
)
INTEGRATION_VERSION: str = _MANIFEST.get("version", "unknown")

# Keys whose values are secrets or network PII. async_redact_data matches by key
# name recursively, so config-entry keys and the device-level keys below are all
# covered. Device *names* are deliberately NOT redacted — they are needed to
# correlate a report and are not secrets.
TO_REDACT = {
    # config entry credentials
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_SHC_CERT,
    CONF_SHC_KEY,
    # network identifiers
    CONF_HOST,
    CONF_HOSTNAME,
    "ip",
    "macAddress",
    "root_device_id",
    "serial",
}


def _device_dump(device: Any) -> dict[str, Any]:
    """One device + the raw state of each of its services (the useful part)."""
    return {
        "id": device.id,
        "root_device_id": device.root_device_id,
        "device_model": device.device_model,
        "manufacturer": device.manufacturer,
        "name": device.name,
        "room_id": device.room_id,
        "serial": device.serial,
        "services": [
            {"id": service.id, "state": service.state}
            for service in device.device_services
        ],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a Bosch SHC config entry."""
    diag: dict[str, Any] = {
        "integration_version": INTEGRATION_VERSION,
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
    }

    container = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    session = container.get(DATA_SESSION) if container else None
    if session is None:
        diag["session"] = "not loaded"
        return diag

    info = session.information
    diag["shc"] = async_redact_data(
        {
            "version": info.version,
            "update_state": info.updateState.name,
            "macAddress": info.macAddress,
            "ip": info.shcIpAddress,
        },
        TO_REDACT,
    )

    devices = list(session.devices)
    diag["device_count"] = len(devices)
    diag["devices"] = [
        async_redact_data(_device_dump(device), TO_REDACT) for device in devices
    ]
    return diag
