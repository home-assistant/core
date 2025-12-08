from __future__ import annotations

import logging
import re
from typing import Any

from rebooterpro_async import RebooterConnectionError, RebooterHttpError

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device_client import async_close_client, async_get_client, build_probe_client
from .models import ConnectSenseConfigEntry, ConnectSenseRuntimeData

DEVICE_PREFIX = "CS-RBTR-"
_SERIAL_RE = re.compile(r"^(\d+)$")
PLATFORMS = ["button"]

_LOGGER = logging.getLogger(__name__)


async def _probe_serial_over_https(hass: HomeAssistant, entry_or_host: ConfigEntry | str) -> str | None:
    """Return the numeric serial from GET /info (device), or None on failure."""
    if isinstance(entry_or_host, str):
        entry = None
        host = (entry_or_host or "").strip()
    else:
        entry = entry_or_host
        host = (entry.data.get(CONF_HOST) or "").strip() if entry else ""

    if not host:
        return None

    client = await (async_get_client(hass, entry) if entry is not None else build_probe_client(hass, host))
    try:
        data: dict[str, Any] | None = await client.get_info()
    except Exception as exc:  # pragma: no cover - logged only
        _LOGGER.debug("GET /info failed for %s: %r", host, exc)
        return None

    device_field = (data or {}).get("device")
    if not isinstance(device_field, str):
        return None

    candidate = device_field[len(DEVICE_PREFIX) :] if device_field.startswith(DEVICE_PREFIX) else device_field
    candidate = candidate.strip()
    if _SERIAL_RE.match(candidate):
        return candidate

    _LOGGER.debug("Unexpected device format in /info: %r", device_field)
    return candidate or None


async def async_setup_entry(hass: HomeAssistant, entry: ConnectSenseConfigEntry) -> bool:
    """Set up the ConnectSense entry."""
    try:
        host = entry.data.get(CONF_HOST)
        if entry.unique_id and host and entry.unique_id == host:
            serial = await _probe_serial_over_https(hass, entry)
            if serial and serial != entry.unique_id:
                hass.config_entries.async_update_entry(
                    entry,
                    unique_id=serial,
                    title=f"Rebooter Pro {serial}",
                )
    except Exception as exc:  # pragma: no cover - defensive logging only
        _LOGGER.debug("Unique_id migration via /info skipped: %s", exc)

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = await async_get_client(hass, entry)
    try:
        await client.get_info()
    except (RebooterConnectionError, RebooterHttpError) as exc:
        raise ConfigEntryNotReady from exc
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Device health check failed: %s", exc)
        raise ConfigEntryNotReady from exc

    entry.runtime_data = ConnectSenseRuntimeData(hass.data[DOMAIN][entry.entry_id])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConnectSenseConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_close_client(hass, entry.entry_id)
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
