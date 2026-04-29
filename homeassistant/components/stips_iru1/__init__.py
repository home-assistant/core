"""STIPS IRU1 Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr

from .catalog import normalize_device_mac
from .const import DOMAIN, PLATFORMS


@dataclass(slots=True)
class StipsIru1RuntimeData:
    """Runtime data for the STIPS IRU1 integration."""

    devices: list[dict[str, Any]]


type StipsIru1ConfigEntry = ConfigEntry[StipsIru1RuntimeData]


def _register_catalog_devices(hass: HomeAssistant, entry: StipsIru1ConfigEntry) -> None:
    """Ensure every IR unit in the catalog has a device registry entry.

    Units with only protocol-AC remotes create no signal-based remote entities; without this,
    Home Assistant would not list them under the integration.
    """
    reg = dr.async_get(hass)
    for device in entry.data.get("devices", []):
        uid = device.get("uniqueName")
        if not uid:
            continue
        name = device.get("name") or uid
        sw = device.get("buildVersion")
        kwargs: dict[str, Any] = {
            "config_entry_id": entry.entry_id,
            "identifiers": {(DOMAIN, str(uid))},
            "name": name,
            "manufacturer": "STIPS",
            "model": "IRU1",
            "sw_version": str(sw) if sw is not None else None,
        }
        mac = normalize_device_mac(device)
        if mac:
            kwargs["connections"] = {(dr.CONNECTION_NETWORK_MAC, mac)}
        area_name = device.get("areaName")
        if area_name:
            kwargs["suggested_area"] = str(area_name)
        reg.async_get_or_create(**kwargs)


async def async_setup_entry(hass: HomeAssistant, entry: StipsIru1ConfigEntry) -> bool:
    """Set up STIPS IRU1 from a config entry."""
    devices = entry.data.get("devices", [])
    if not isinstance(devices, list):
        raise ConfigEntryError("Invalid devices data in config entry")

    entry.runtime_data = StipsIru1RuntimeData(devices=devices)

    _register_catalog_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StipsIru1ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
