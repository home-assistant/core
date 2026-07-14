"""System Health support for Bosch Smart Home Camera.

Contributes integration connectivity status to the HA System Health dashboard
(Settings → System → System Health). Power-users can see cloud reachability,
FCM push status, and loaded camera count alongside other integrations.
"""

from __future__ import annotations

import math
import time
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

CLOUD_HEALTH_URL = "https://residential.cbs.boschsecurity.com/"

# Vanity marker: confirms Platinum-tier code is running.
_PLATINUM_VERSION = "v12.0.0+"


@callback  # type: ignore[untyped-decorator]
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system-health callbacks."""
    register.async_register_info(
        system_health_info,
        "/config/integrations/integration/bosch_shc_camera",
    )


def _first_loaded_coordinator(hass: HomeAssistant) -> Any | None:
    """Return the runtime_data of the first loaded bosch_shc_camera config entry.

    Returns None when no entry is loaded (e.g. during startup or if the
    integration has been removed).
    """
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None
    coord = getattr(entries[0], "runtime_data", None)
    return coord


def _format_ago(last_push: float) -> str:
    """Format a monotonic timestamp as 'Xs ago' or 'never'.

    Uses float('-inf') as the sentinel for "push has never happened".
    Any other infinite value (e.g. float('+inf') from a corrupt state) is
    treated as 'never' rather than raising OverflowError.
    """
    if math.isinf(last_push):
        return "never"
    delta = int(time.monotonic() - last_push)
    return f"{delta}s ago"


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return info for the System Health dashboard."""
    coord = _first_loaded_coordinator(hass)

    # Cloud reachability is always checked — works even without a coordinator.
    can_reach = system_health.async_check_can_reach_url(hass, CLOUD_HEALTH_URL)

    if coord is None:
        return {
            "can_reach_cloud": can_reach,
            "cameras_loaded": 0,
            "fcm_push_active": "no integration loaded",
            "platinum_quality": _PLATINUM_VERSION,
        }

    fcm_running: bool = getattr(coord, "_fcm_running", False)
    fcm_push_active = "healthy" if fcm_running else "degraded"

    cameras_data: dict[str, Any] = getattr(coord, "data", {}) or {}
    cameras_loaded = len(cameras_data)

    last_push: float = getattr(coord, "_fcm_last_push", float("-inf"))
    last_fcm_push_ago = _format_ago(last_push)

    return {
        "can_reach_cloud": can_reach,
        "cameras_loaded": cameras_loaded,
        "fcm_push_active": fcm_push_active,
        "last_fcm_push_ago": last_fcm_push_ago,
        "platinum_quality": _PLATINUM_VERSION,
    }
