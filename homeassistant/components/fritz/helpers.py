"""Helpers for AVM FRITZ!Box."""

from __future__ import annotations

from collections.abc import ValuesView
import logging

from .models import FritzDevice

_LOGGER = logging.getLogger(__name__)


def _is_tracked(mac: str, current_devices: ValuesView[set[str]]) -> bool:
    """Check if device is already tracked."""
    return any(mac in tracked for tracked in current_devices)


def device_filter_out_from_trackers(
    mac: str,
    device: FritzDevice,
    current_devices: ValuesView[set[str]],
) -> bool:
    """Check if device should be filtered out from trackers."""
    reason: str | None = None
    if device.ip_address == "":
        reason = "Missing IP"
    elif _is_tracked(mac, current_devices):
        reason = "Already tracked"

    if reason:
        _LOGGER.debug(
            "Skip adding device %s [%s], reason: %s", device.hostname, mac, reason
        )
    return bool(reason)


def _ha_is_stopping(activity: str) -> None:
    """Inform that HA is stopping."""
    _LOGGER.warning("Cannot execute %s: HomeAssistant is shutting down", activity)
