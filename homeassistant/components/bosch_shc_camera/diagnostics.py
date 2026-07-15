"""Diagnostics support for Bosch Smart Home Camera (Quality-Scale Gold).

Returns a redacted JSON snapshot of the integration state when the user
clicks "Download diagnostics" in Settings → Devices & Services. Replaces
the manual log-collection workflow for bug reports.

Sensitive fields (bearer / refresh tokens, FCM IDs, SMB credentials, MAC
addresses, cloud IDs) are redacted via homeassistant.diagnostics.async_redact_data.
"""

from collections.abc import Sized
import json
import pathlib
import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BoschCameraConfigEntry

_MANIFEST: dict[str, Any] = json.loads(
    (pathlib.Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
)
INTEGRATION_VERSION: str = _MANIFEST.get("version", "unknown")

TO_REDACT = {
    # Tokens / OAuth credentials
    "bearer_token",
    "refresh_token",
    "access_token",
    "id_token",
    # FCM / Firebase secrets — async_redact_data walks dicts recursively, so
    # these top-level keys cover the nested fcm_credentials.* substructures.
    "fcm_token",
    "fcm_config",
    "fcm_credentials",
    "api_key",
    "vapid_key",
    "auth",
    "endpoint",
    "fid",
    "private",
    "public",
    "secret",
    "p256dh",
    "android_id",
    "security_token",
    "token",
    # SMB / NAS credentials
    "password",
    "smb_password",
    "smb_username",
    "smb_server",
    "smb_share",
    "smb_base_path",
    # Frigate/external-recorder persistent RTSP front-door credentials.
    # Regression (bug-hunt 2026-07-03): async_redact_data matches keys
    # EXACTLY, so the generic "token"/"auth" entries above never caught
    # "frigate_token" — the front-door auth token, Basic-Auth username, and
    # allowed-IP list leaked in plaintext into every diagnostics export
    # (a user-facing feature routinely pasted into public bug reports).
    "frigate_token",
    "frigate_basic_user",
    "frigate_ip_allowlist",
    # Stream / RTSP URLs (contain proxy session credentials)
    "rtspsUrl",
    "rtsps_url",
    "live_rtsps",
    "live_proxy",
    # Network identifiers (PII)
    "mac",
    "cloud_id",
    "videoInputId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoschCameraConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Bosch SHC Camera config entry."""
    coord = getattr(entry, "runtime_data", None)

    # Per-camera summary — only fields safe to share, no secrets, no rtsps URLs
    now = time.monotonic()
    cameras: list[dict[str, Any]] = []
    if coord is not None and coord.data:
        offline_since: dict[str, float] = getattr(coord, "offline_since", {})
        stream_error_count: dict[str, int] = getattr(coord, "stream_error_count", {})
        stream_fell_back: dict[str, bool] = getattr(coord, "stream_fell_back", {})
        session_stale: dict[str, bool] = getattr(coord, "session_stale", {})
        for cam_id, cdata in coord.data.items():
            info = cdata.get("info", {})
            live = cdata.get("live", {})
            since = offline_since.get(cam_id)
            cameras.append(
                async_redact_data(
                    {
                        "cam_id_prefix": cam_id[:8],
                        "title": info.get("title"),
                        "model": info.get("hardwareVersion"),
                        "firmware": info.get("firmwareVersion"),
                        "status": cdata.get("status"),
                        "online": cdata.get("online"),
                        "privacy_mode": cdata.get("privacy_mode"),
                        "events_today_count": len(cdata.get("events", [])),
                        "live_connection_type": live.get("connectionType"),
                        "live_age_seconds": live.get("age_seconds"),
                        # stream health — useful for diagnosing stream-restart loops
                        "stream_error_count": stream_error_count.get(cam_id, 0),
                        "stream_fell_back": stream_fell_back.get(cam_id, False),
                        "session_stale": session_stale.get(cam_id, False),
                        "offline_since_seconds": int(now - since)
                        if since is not None
                        else None,
                    },
                    TO_REDACT,
                )
            )

    # Not a set[str] anymore — coord.stream_warming is a StreamWarmingView
    # facade (session_state.py) since the Phase 1 coordinator rewrite. Sized
    # is the correct minimal type for the only operation used here, len().
    stream_warming: Sized = getattr(coord, "stream_warming", set())

    return {
        "integration_version": INTEGRATION_VERSION,
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "running": coord is not None,
            "last_update_success": getattr(coord, "last_update_success", None),
            "fcm_running": getattr(coord, "fcm_running", None),
            "fcm_healthy": getattr(coord, "fcm_healthy", None),
            "auth_outage_count": getattr(coord, "auth_outage_count", None),
            "scan_interval": getattr(
                getattr(coord, "update_interval", None), "total_seconds", lambda: None
            )(),
            "stream_warming_count": len(stream_warming),
        },
        "cameras": cameras,
    }
