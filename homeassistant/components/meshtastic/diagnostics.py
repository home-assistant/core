"""Diagnostics support for the Meshtastic integration.

The download is a support artefact, so it carries everything that explains a
misbehaving mesh - the gateway identity, the state of the TCP link, the node
table and the errors that led to the current state - and nothing that would
compromise the mesh once the file is attached to a bug report.  Channel
pre-shared keys, the node's private and admin keys, administration session
passkeys and the Wi-Fi and MQTT credentials are redacted wherever they appear,
and so are the coordinates of every node unless the user asked for them.

Redaction is by key, but the node's address also turns up in the *text* of the
errors this integration reports, so the finished dump is scrubbed of it as
well.
"""

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import AnyDeviceEntry

from . import MeshtasticConfigEntry
from .const import (
    CONF_INCLUDE_LOCATION,
    DEFAULT_INCLUDE_LOCATION,
    DOMAIN,
    gateway_device_id,
)
from .coordinator import MeshtasticCoordinator

#: Secret material.  The models this integration publishes never carry any of
#: it, but the config entry and any raw record that is ever added to the dump
#: might, and both the protobuf (snake case) and the library's dict (camel
#: case) spelling have to be covered.
TO_REDACT_SECRETS: frozenset[str] = frozenset(
    {
        CONF_HOST,
        "admin_key",
        "adminKey",
        "admin_keys",
        "adminKeys",
        "password",
        "private_key",
        "privateKey",
        "psk",
        "public_key",
        "publicKey",
        "session_passkey",
        "sessionPasskey",
        "wifi_psk",
        "wifiPsk",
        "wifi_ssid",
        "wifiSsid",
    }
)

#: Anything that pins a node to a spot on the map.
TO_REDACT_LOCATION: frozenset[str] = frozenset(
    {
        "latitude",
        "latitudeI",
        "latitude_i",
        "longitude",
        "longitudeI",
        "longitude_i",
    }
)


def _to_redact(entry: ConfigEntry) -> frozenset[str]:
    """Return the keys to redact for this entry."""
    if entry.options.get(CONF_INCLUDE_LOCATION, DEFAULT_INCLUDE_LOCATION):
        return TO_REDACT_SECRETS
    return TO_REDACT_SECRETS | TO_REDACT_LOCATION


def _entry_info(entry: ConfigEntry, to_redact: frozenset[str]) -> dict[str, Any]:
    """Return the parts of the config entry worth reporting."""
    return {
        "title": entry.title,
        "version": entry.version,
        "minor_version": entry.minor_version,
        "source": entry.source,
        "unique_id": entry.unique_id,
        "data": async_redact_data(dict(entry.data), to_redact),
        "options": async_redact_data(dict(entry.options), to_redact),
    }


def _errors(
    coordinator: MeshtasticCoordinator, stats: dict[str, Any]
) -> dict[str, Any]:
    """Return what is known about the failures behind the current state.

    ``last_exception`` is the error the coordinator last published to entities,
    ``dead_reason`` is why the client last declared the link dead, and the
    counters say whether this is a one-off or a node that keeps dropping us.
    """
    last_exception = coordinator.last_exception
    return {
        "last_update_success": coordinator.last_update_success,
        "last_exception": None if last_exception is None else repr(last_exception),
        "dead_reason": stats["dead_reason"],
        "reconnect_attempts": stats["reconnect_attempts"],
        "short_connections": stats["short_connections"],
        "missed_heartbeats": stats["missed_heartbeats"],
        "circuit_breaker_open": stats["circuit_breaker_open"],
    }


def _redact_host_text(value: Any, host: str) -> Any:
    """Return ``value`` with every literal occurrence of ``host`` redacted."""
    if isinstance(value, str):
        return value.replace(host, REDACTED)
    if isinstance(value, dict):
        return {key: _redact_host_text(item, host) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_host_text(item, host) for item in value]
    return value


def _redacted_dump(dump: dict[str, Any], host: str) -> dict[str, Any]:
    """Return the finished dump with the node's address taken back out.

    ``async_redact_data`` matches keys, and that is not enough here: every
    connection error the client raises carries the address as a translation
    placeholder, so the rendered message ends up inside ``dead_reason`` and
    inside the coordinator's last exception, where no key names it.  Redacting
    ``host`` and leaving those would publish the address anyway.
    """
    redacted: dict[str, Any] = _redact_host_text(dump, host) if host else dump
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeshtasticConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = entry.runtime_data.client
    coordinator = entry.runtime_data.coordinator
    to_redact = _to_redact(entry)
    gateway = coordinator.gateway_or_none
    stats = client.stats()

    return _redacted_dump(
        {
            "entry": _entry_info(entry, to_redact),
            "gateway": None if gateway is None else gateway.as_dict(),
            "connection": async_redact_data(stats, to_redact),
            "errors": _errors(coordinator, stats),
            "nodes": async_redact_data(
                {
                    node_id: node.as_dict()
                    for node_id, node in coordinator.nodes.items()
                },
                to_redact,
            ),
        },
        client.host,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: MeshtasticConfigEntry, device_entry: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for one gateway or mesh-node device."""
    client = entry.runtime_data.client
    coordinator = entry.runtime_data.coordinator
    to_redact = _to_redact(entry)
    gateway = coordinator.gateway_or_none

    identifier = next(
        (value for domain, value in device_entry.identifiers if domain == DOMAIN), None
    )
    # A node sub-device is "<gateway id>_<node id>"; the gateway itself is just
    # "<gateway id>".  Either way the trailing id is the node to report on.
    node_id = None if identifier is None else identifier.rsplit("_", 1)[-1]
    is_gateway = gateway is not None and identifier == gateway_device_id(
        gateway.node_num
    )
    node = None if node_id is None else coordinator.get_node(node_id)

    return _redacted_dump(
        {
            "identifier": identifier,
            "is_gateway": is_gateway,
            "gateway": None if gateway is None or not is_gateway else gateway.as_dict(),
            "connection": (
                async_redact_data(client.stats(), to_redact) if is_gateway else None
            ),
            "node": (
                None if node is None else async_redact_data(node.as_dict(), to_redact)
            ),
        },
        client.host,
    )
