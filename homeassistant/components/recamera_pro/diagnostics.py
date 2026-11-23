"""Diagnostics support for reCamera Pro."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import RecameraCoordinator
from .source_state import DetectionState

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "host",
    "mac_address",
    "password",
    "private_key",
    "spassword",
    "secret",
    "serial_number",
    "srequesttoken",
    "surl",
    "token",
    "username",
}


def _redact(value: Any) -> Any:
    """Recursively redact diagnostics values."""
    if isinstance(value, dict):
        return {
            str(key): (
                "[redacted]"
                if (
                    str(key).lower() in SENSITIVE_KEYS
                    or str(key)
                    .lower()
                    .endswith(("_password", "_token", "_secret", "_cookie"))
                )
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _source_diagnostics(state: DetectionState) -> dict[str, Any]:
    """Return safe per-source diagnostics."""
    observation = state.last_observation
    event = state.last_event
    return {
        "health": state.health,
        "reason": state.reason,
        "last_received": (
            state.last_received.isoformat() if state.last_received else None
        ),
        "last_observation": (
            {
                "source_id": observation.source_id,
                "class_name": observation.class_name,
                "class_id": observation.class_id,
                "class_key": observation.class_key,
                "task_type": observation.task_type,
                "confidence": observation.confidence,
                "occurred_at": observation.timestamp.isoformat(),
                "received_at": observation.received_at.isoformat(),
                "clock_valid": observation.clock_valid,
                "device_wall_ms": observation.device_wall_ms,
                "metadata": observation.metadata,
                "raw_json": observation.raw_json,
            }
            if observation
            else None
        ),
        "last_event": (
            {
                "event_id": event.event_id,
                "class_key": event.class_key,
                "task_type": event.task_type,
                "metadata": event.metadata,
                "raw_json": event.raw_json,
                "occurred_at": event.timestamp.isoformat(),
                "received_at": event.received_at.isoformat(),
                "clock_valid": event.clock_valid,
            }
            if event
            else None
        ),
        "active_class_keys": sorted(state.active_classes),
        "event_serial": state.event_serial,
        "clock_invalid": state.clock_invalid,
    }


def _media_profile_diagnostics(profile: dict[str, Any]) -> dict[str, Any]:
    """Return media profile details without credentials or stream URLs."""
    stream = profile.get("stream") or {}
    encode = profile.get("encode") or {}
    rtsp = stream.get("rtsp") or {}
    return {
        "rtsp_enabled": rtsp.get("iEnabled") == 1,
        "rtsp_auth_enabled": rtsp.get("iAuthType") == 1,
        "codec": encode.get("sOutputDataType"),
        "width": encode.get("iWidth"),
        "height": encode.get("iHeight"),
        "fps": encode.get("sFrameRate"),
        "gop": encode.get("iGOP"),
        "rc_mode": encode.get("sRCMode"),
        "max_rate": encode.get("iMaxRate"),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return recursively redacted diagnostics."""
    coordinator: RecameraCoordinator | None = getattr(
        config_entry, "runtime_data", None
    )
    entry_data = {
        key: value for key, value in config_entry.data.items() if key != CONF_PASSWORD
    }
    entry_data["password_set"] = bool(config_entry.data.get(CONF_PASSWORD))
    if coordinator is None:
        return _redact(
            {
                "entry": {
                    "version": config_entry.version,
                    "data": _redact(entry_data),
                    "options": _redact(dict(config_entry.options)),
                },
                "runtime": {
                    "coordinator_loaded": False,
                    "websocket_connected": False,
                    "stream_ready": False,
                },
            }
        )
    data = coordinator.data
    return _redact(
        {
            "entry": {
                "version": config_entry.version,
                "data": _redact(entry_data),
                "options": _redact(dict(config_entry.options)),
            },
            "runtime": {
                "websocket_connected": (data.websocket_connected if data else False),
                "stream_ready": data.stream_ready if data else False,
                "last_stream_message": (
                    data.last_stream_message.isoformat()
                    if data and data.last_stream_message
                    else None
                ),
                "visual": (_source_diagnostics(data.visual) if data else None),
                "audio": (_source_diagnostics(data.audio) if data else None),
                "class_catalog": (
                    [item.as_dict() for item in data.class_catalog.values()]
                    if data
                    else []
                ),
                "motion": (
                    {
                        "installed": data.motion.installed,
                        "running": data.motion.running,
                        "motion": data.motion.motion,
                        "app_health": data.motion.app_health,
                        "reason": data.motion.reason,
                        "error": data.motion.error,
                        "last_confirmed": (
                            data.motion.last_confirmed.isoformat()
                            if data.motion.last_confirmed
                            else None
                        ),
                        "config_health": data.motion.config_health,
                        "config_error": data.motion.config_error,
                        "config_last_confirmed": (
                            data.motion.config_last_confirmed.isoformat()
                            if data.motion.config_last_confirmed
                            else None
                        ),
                        "last_seen": (
                            data.motion.last_seen.isoformat()
                            if data.motion.last_seen
                            else None
                        ),
                        "config": dict(data.motion.config),
                        "event_id": data.motion.event_id,
                        "sequence": data.motion.sequence,
                    }
                    if data
                    else None
                ),
            },
            "device": {
                "model": data.info.base_plate_model if data else None,
                "sensor_model": data.info.sensor_model if data else None,
                "hardware_version": (data.info.hardware_version if data else None),
                "firmware_version": (data.info.firmware_version if data else None),
                "serial_number": (data.info.serial_number if data else None),
            },
            "capabilities": _redact(data.capabilities if data else {}),
            "device_capture": coordinator.capture_controller.diagnostics(),
            "media_profiles": (
                {
                    name: _media_profile_diagnostics(profile)
                    for name, profile in data.media_profiles.items()
                }
                if data
                else {}
            ),
            "media_errors": data.media_errors if data else {},
            "appmgr_transport": coordinator.client.appmgr_transport,
            "firmware": {
                "installed_version": (coordinator.firmware_update.installed_version),
                "latest_version": coordinator.firmware_update.latest_version,
                "published_version": (coordinator.firmware_update.published_version),
                "target_version": coordinator.firmware_update.target_version,
                "available": coordinator.firmware_update.available,
                "in_progress": coordinator.firmware_update.in_progress,
                "percentage": coordinator.firmware_update.update_percentage,
                "status": coordinator.firmware_update.status,
                "operation": coordinator.firmware_update.operation,
                "last_checked": (
                    coordinator.firmware_update.last_checked.isoformat()
                    if coordinator.firmware_update.last_checked
                    else None
                ),
            },
        }
    )
