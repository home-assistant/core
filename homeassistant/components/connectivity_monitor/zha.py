"""ZHA (Zigbee Home Automation) device access helpers for Connectivity Monitor."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

ZHA_DOMAIN = "zha"


def _get_zha_gateway(hass: HomeAssistant):
    """Return the ZHA gateway object from hass.data, or None.

    Tries multiple paths to handle all known HA versions:
      - HA 2023.x : hass.data["zha"][entry_id].gateway
      - HA 2024.x : hass.data["zha"][entry_id].gateway_proxy.gateway
      - Fallback  : hass.data["zha"][entry_id] itself has a 'devices' attr
    """
    zha_data = hass.data.get(ZHA_DOMAIN)
    if not zha_data:
        _LOGGER.debug(
            "ZHA domain '%s' not in hass.data. Available keys: %s",
            ZHA_DOMAIN,
            list(hass.data.keys()),
        )
        return None

    _LOGGER.debug("ZHA hass.data entry type: %s", type(zha_data).__name__)

    # Normalise: iterate over dict values, or treat the object itself as one entry
    entries = zha_data.values() if isinstance(zha_data, dict) else [zha_data]

    for entry_data in entries:
        _LOGGER.debug("Inspecting ZHA entry_data type: %s", type(entry_data).__name__)

        # HA 2024+: ZHAData.gateway_proxy.gateway
        gw_proxy = getattr(entry_data, "gateway_proxy", None)
        if gw_proxy is not None:
            gateway = getattr(gw_proxy, "gateway", None)
            if gateway is not None and hasattr(gateway, "devices"):
                _LOGGER.debug("ZHA gateway found via gateway_proxy.gateway")
                return gateway

        # HA 2023.x: ZHAData.gateway
        gateway = getattr(entry_data, "gateway", None)
        if gateway is not None and hasattr(gateway, "devices"):
            _LOGGER.debug("ZHA gateway found via entry_data.gateway")
            return gateway

        # In some versions entry_data itself is the gateway
        if hasattr(entry_data, "devices"):
            _LOGGER.debug("ZHA entry_data itself has 'devices' — treating as gateway")
            return entry_data

    _LOGGER.debug("ZHA gateway object not found via hass.data paths")
    return None


def _last_seen_to_timestamp(last_seen) -> float | None:
    """Normalise last_seen to a Unix float timestamp.

    ZHA stores last_seen as either:
      - a float/int Unix timestamp (zigpy 0.x)
      - a datetime object (zigpy 0.60+)
    """
    if last_seen is None:
        return None
    if isinstance(last_seen, (int, float)):
        return float(last_seen)
    # datetime object
    if hasattr(last_seen, "timestamp"):
        try:
            return last_seen.timestamp()
        except AttributeError, TypeError:
            pass
    return None


def _build_registry_name_map(hass: HomeAssistant) -> dict[str, str]:
    """Build a ieee -> display_name map from the HA device registry.

    Uses name_by_user (user-assigned rename) when available, otherwise the
    auto-generated device name that ZHA stores at pairing time.
    """
    name_map: dict[str, str] = {}
    try:
        device_registry = dr.async_get(hass)
        for device_entry in device_registry.devices.values():
            for identifier in device_entry.identifiers:
                if identifier[0] == ZHA_DOMAIN:
                    ieee = identifier[1]
                    name_map[ieee] = (
                        device_entry.name_by_user or device_entry.name or ieee
                    )
                    break
    except (AttributeError, RuntimeError) as err:
        _LOGGER.debug("Could not build registry name map: %s", err)
    return name_map


async def async_get_zha_devices(hass: HomeAssistant) -> list[dict]:
    """Return a list of all non-coordinator ZHA devices.

    Tries the ZHA gateway first (gives us last_seen).
    Falls back to the device registry if the internal gateway is inaccessible
    (no last_seen in that case, but device selection still works).

    In both cases, the display name is taken from the HA device registry so it
    matches exactly what the user sees in the ZHA device list.
    """
    devices = []

    # Build ieee -> display name from device registry (authoritative for names)
    registry_names = _build_registry_name_map(hass)

    # ── Primary path: ZHA gateway ─────────────────────────────────────────────
    try:
        gateway = _get_zha_gateway(hass)
        if gateway is not None:
            for ieee, device in gateway.devices.items():
                if getattr(device, "is_coordinator", False):
                    continue
                ieee_str = str(ieee)
                # Prefer registry display name; fall back to zigpy device.name
                display_name = (
                    registry_names.get(ieee_str)
                    or getattr(device, "name", None)
                    or ieee_str
                )
                devices.append(
                    {
                        "ieee": ieee_str,
                        "name": display_name,
                        "model": getattr(device, "model", None),
                        "manufacturer": getattr(device, "manufacturer", None),
                        "last_seen": _last_seen_to_timestamp(
                            getattr(device, "last_seen", None)
                        ),
                    }
                )
            if devices:
                _LOGGER.debug("ZHA devices from gateway: %d found", len(devices))
                return devices
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning("ZHA gateway enumeration failed: %s", err)

    # ── Fallback path: HA device registry ────────────────────────────────────
    _LOGGER.debug("Falling back to device registry for ZHA device list")
    try:
        device_registry = dr.async_get(hass)
        for device_entry in device_registry.devices.values():
            for identifier in device_entry.identifiers:
                if identifier[0] == ZHA_DOMAIN:
                    ieee = identifier[1]
                    last_seen = _last_seen_to_timestamp(
                        getattr(device_entry, "last_seen", None)
                    )
                    devices.append(
                        {
                            "ieee": ieee,
                            "name": (
                                device_entry.name_by_user or device_entry.name or ieee
                            ),
                            "model": device_entry.model,
                            "manufacturer": device_entry.manufacturer,
                            "last_seen": last_seen,
                        }
                    )
                    break
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning("Device registry ZHA fallback failed: %s", err)

    _LOGGER.debug("ZHA devices from device registry fallback: %d found", len(devices))
    return devices


async def async_get_zha_device_last_seen(
    hass: HomeAssistant, ieee: str
) -> float | None:
    """Return the last_seen Unix timestamp for a ZHA device by IEEE address.

    Tries the ZHA gateway first; falls back to the device registry.
    """
    # ── Primary: ZHA gateway ──────────────────────────────────────────────────
    try:
        gateway = _get_zha_gateway(hass)
        if gateway is not None:
            for dev_ieee, device in gateway.devices.items():
                if str(dev_ieee) == ieee:
                    return _last_seen_to_timestamp(getattr(device, "last_seen", None))
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Failed to get last_seen from ZHA gateway for %s: %s", ieee, err
        )

    # ── Fallback: device registry last_seen (HA 2024.4+) ─────────────────────
    try:
        device_registry = dr.async_get(hass)
        for device_entry in device_registry.devices.values():
            for identifier in device_entry.identifiers:
                if identifier[0] == ZHA_DOMAIN and identifier[1] == ieee:
                    return _last_seen_to_timestamp(
                        getattr(device_entry, "last_seen", None)
                    )
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Failed to get last_seen from device registry for %s: %s", ieee, err
        )

    return None
