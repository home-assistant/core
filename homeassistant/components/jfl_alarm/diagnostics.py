"""Diagnostics download — everything a bug report needs and nothing that identifies the house.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

AGENTS.md §4 forbids the serial, IMEI, MAC, account numbers, user codes and the panel password from
ever reaching a log or a diagnostics dump. Every one of them is redacted here — but the serial and
MAC are redacted **consistently**, by hashing rather than by blanking, so a dump with three panels
in it can still be read: the same panel shows the same token throughout, and no token can be turned
back into a serial.

The raw-frame ring buffer is the reason this file matters. A user who reports "the fence state is
wrong" hands over fifty frames of real traffic with it, which is the difference between guessing and
re-decoding the actual bytes. But `pyjfl.RawFrame.as_dict()` renders the frame exactly as it crossed
the wire, on purpose — its own docstring says the point is to re-decode it by hand, so it has no
business deciding what a caller should hide. A `0x21` connection frame carries the serial, IMEI and
MAC as plain ASCII at fixed offsets (`docs/protocol/commands.md`), and that frame is deliberately
captured into the ring buffer (`pyjfl`'s own `_identify`, so a dump of a reconnect shows the
handshake). `_redact_frame_hex` below is where this integration's redaction policy actually applies
to it, the same as every other identifier in this file — hashing rather than blanking, and reusing
`_token` so the number matches the one in `identity.mac`/`identity.imei`/the top-level `serial`.
"""

import hashlib
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

from .const import CONF_CODE_ARM_REQUIRED, DOMAIN

# The 0x21 connection frame's command byte and the absolute byte ranges of the identifiers it
# carries in cleartext ASCII, per docs/protocol/commands.md's layout table (also documented in
# pyjfl's decode_connection). Offsets are absolute into the frame's raw bytes, matching
# pyjfl.RawFrame.data — the same bytes decode_connection itself slices.
_CONNECTION_FRAME_CMD = 0x21
_SERIAL_RANGE = slice(4, 14)
_IMEI_RANGE = slice(14, 29)
_MAC_RANGE = slice(29, 41)

if TYPE_CHECKING:
    from pyjfl import PanelStatus

    from homeassistant.helpers.device_registry import DeviceEntry

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator


def _token(value: str) -> str:
    """Return a stable, non-reversible stand-in for an identifier.

    Blanking every serial to `**REDACTED**` makes a multi-panel dump unreadable — three panels
    become indistinguishable. A truncated hash keeps them apart and still tells no one anything.
    """
    if not value:
        return ""
    return "id:" + hashlib.sha256(value.encode()).hexdigest()[:12]


def _redact_frame_hex(data: bytes) -> str:
    """Render one raw frame's bytes as hex, with a `0x21` frame's identifiers replaced by tokens.

    Every other frame type is rendered untouched — `hex()` on the raw bytes, same as
    `RawFrame.as_dict()` itself. A `0x21` frame instead renders as three hex runs joined by
    bracketed tokens in place of the serial/IMEI/MAC ranges, each the same `_token()` hash used
    everywhere else in this file, so the number matches `identity.mac`/`identity.imei`/the
    top-level `serial` in the same dump. Deliberately **not** re-encoded as fake hex bytes: doing
    that would leave the frame's trailing checksum silently describing a payload that no longer
    exists, which reads as "this is what the panel sent" to someone re-decoding it by hand —
    exactly the failure mode redaction is supposed to prevent. A bracketed token cannot be mistaken
    for wire bytes.

    Too short to safely contain a `0x21` frame's fixed ranges is left alone; a frame that short
    cannot be a genuine connection frame, so there is nothing here to redact.
    """
    if (
        len(data) <= 3
        or data[3] != _CONNECTION_FRAME_CMD
        or len(data) < _MAC_RANGE.stop
    ):
        return data.hex(" ")

    def _hex(raw_range: bytes) -> str:
        return raw_range.hex(" ")

    def _masked(raw_range: bytes) -> str:
        text = raw_range.decode("latin-1").rstrip("\xff\x00")
        return f"[{_token(text)}]" if text else "[empty]"

    return (
        f"{_hex(data[: _SERIAL_RANGE.start])} "
        f"{_masked(bytes(data[_SERIAL_RANGE]))} "
        f"{_masked(bytes(data[_IMEI_RANGE]))} "
        f"{_masked(bytes(data[_MAC_RANGE]))} "
        f"{_hex(data[_MAC_RANGE.stop :])}"
    ).strip()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JflConfigEntry
) -> dict[str, Any]:
    """Everything about the listener and its panels."""
    runtime = entry.runtime_data
    return {
        "listener": {
            "host": runtime.server.host,
            "port": runtime.server.port,
            "running": runtime.server.is_running,
            "keepalive_minutes": runtime.server.keepalive_minutes,
            "unknown_panel_policy": runtime.server.unknown_panels,
        },
        "options": dict(entry.options),
        "panels": [
            _panel_diagnostics(coordinator)
            for coordinator in runtime.coordinators.values()
        ],
        "pending_panels": [
            {
                "serial": _token(serial),
                "model": info.spec.name,
                "model_byte": info.model_byte,
            }
            for serial, info in runtime.server.pending_panels.items()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: JflConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Just the one panel, for a bug report about a single device.

    Per **device** and not per subentry: Home Assistant has no subentry-level diagnostics hook, and
    the device page is where a user looking at one misbehaving panel already is. A partition or
    fence sub-device resolves to its parent panel, because the interesting state lives there.
    """
    serials = {
        identifier[1].split("-", 1)[0]
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    }
    coordinators = [
        coordinator
        for serial, coordinator in entry.runtime_data.coordinators.items()
        if serial in serials
    ]
    if not coordinators:
        return {"serial": _token(next(iter(serials), "")), "loaded": False}
    return _panel_diagnostics(coordinators[0])


def _panel_diagnostics(coordinator: JflPanelCoordinator) -> dict[str, Any]:
    """One panel: identity (redacted), capabilities, current state and recent frames."""
    state = coordinator.data
    info = state.connection
    return {
        "serial": _token(coordinator.serial),
        "connected": coordinator.link.connected,
        "available": state.available,
        "read_only": coordinator.read_only,
        "commands_enabled": coordinator.commands_enabled,
        "auth_blocked": coordinator.auth_blocked,
        # Whether a Home Assistant code is set, never the code itself. Reporting the boolean is
        # what makes "why does disarming ask me for a code?" answerable from a dump; reporting the
        # code would put the thing that protects the house into a file the user emails around.
        "code_configured": bool(coordinator.subentry.data.get(CONF_CODE)),
        "code_arm_required": bool(
            coordinator.subentry.data.get(CONF_CODE_ARM_REQUIRED)
        ),
        "status_interval": coordinator.status_interval,
        "unknown_packets": state.unknown_packets,
        "last_event_at": state.last_event_at.isoformat()
        if state.last_event_at
        else None,
        "last_event_code": state.last_event_code,
        "identity": {
            "model": state.spec.name,
            "model_byte": info.model_byte if info else None,
            "firmware": info.firmware if info else None,
            "verified_on_hardware": state.spec.verified_on_hardware,
            # Redacted: identifies the installation, and none of it helps decode a frame.
            "mac": _token(info.mac) if info else None,
            "imei": _token(info.imei) if info else None,
        },
        # The merged view — model ceiling, status frame and programming — not the model table on its
        # own, so a bug report shows what the integration actually decided the panel can do.
        "capabilities": {
            "partitions": coordinator.capabilities.partitions,
            "zones": coordinator.capabilities.zones,
            "pgms": coordinator.capabilities.pgms,
            "has_fence": coordinator.capabilities.has_fence,
            "detected_fence_pgm": coordinator.capabilities.detected_fence_pgm,
            "configured_fence_pgm": coordinator.configured_fence_pgm,
        },
        "status": _status_diagnostics(state.status),
        "discovered": {
            "partitions": sorted(coordinator.discovered.partitions),
            "zones": sorted(coordinator.discovered.zones),
            "fence": coordinator.discovered.fence,
            "fence_alarm": coordinator.discovered.fence_alarm,
            "fence_state": coordinator.discovered.fence_state,
            "fence_event": coordinator.discovered.fence_event,
        },
        "frames": [
            {**frame.as_dict(), "hex": _redact_frame_hex(frame.data)}
            for frame in coordinator.link.frames
        ],
    }


def _status_diagnostics(status: PanelStatus | None) -> dict[str, Any] | None:
    """Render the decoded status frame field by field, with nothing identifying left in it."""
    if status is None:
        return None
    return {
        "clock": status.clock,
        "battery_volts": round(status.battery_volts, 2),
        "programming_checksum": status.programming_checksum.hex().upper(),
        "pgm": status.pgm,
        "pgm_high": status.pgm_high,
        "siren": status.siren,
        "updating": status.updating,
        "fence": {
            "raw": status.fence.raw,
            "present": status.fence.present,
            "armed": status.fence.armed,
            "triggered": status.fence.triggered,
            "ready": status.fence.ready,
        },
        "fence_permissions": status.fence_permissions.raw,
        "partitions": [
            {
                "number": index,
                "raw": partition.raw,
                "programmed": partition.programmed,
                "armed": partition.armed,
                "armed_stay": partition.armed_stay,
                "triggered": partition.triggered,
            }
            for index, partition in enumerate(status.partitions, start=1)
        ],
        "partition_permissions": [
            permission.raw for permission in status.partition_permissions
        ],
        "zones": [
            {
                "number": zone.number,
                "status": zone.status.name.lower(),
                "may_bypass": zone.may_bypass,
            }
            for zone in status.zones
            if zone.status.exists
        ],
        "problems": sorted(flag.name.lower() for flag in status.problems.active),
    }
