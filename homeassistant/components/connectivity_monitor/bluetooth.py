"""Bluetooth device access helpers for Connectivity Monitor."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

BLUETOOTH_DOMAIN = "bluetooth"


def _normalize_address(address: str | None) -> str:
    """Normalize a Bluetooth address for stable matching."""
    return (address or "").upper()


def _merge_device(base: dict, update: dict) -> dict:
    """Merge Bluetooth device details, preferring richer values."""
    merged = dict(base)
    for key, value in update.items():
        if value in (None, "", [], {}, ()):  # keep existing richer values
            continue
        if key == "rssi":
            current = merged.get("rssi")
            if current is None or value > current:
                merged[key] = value
            continue
        merged[key] = value
    return merged


async def async_get_bluetooth_devices(hass: HomeAssistant) -> list[dict]:
    """Return Bluetooth devices from discovery cache, merged with registry data.

    Many BLE devices are visible to Home Assistant only as scanner discoveries and
    do not have a device-registry entry until another integration claims them.
    To support these devices, enumerate the Bluetooth discovery cache first and
    enrich it with any matching device-registry metadata.
    """
    devices_by_address: dict[str, dict] = {}

    try:
        for connectable in (False, True):
            for service_info in bluetooth.async_discovered_service_info(
                hass, connectable=connectable
            ):
                bt_address = _normalize_address(getattr(service_info, "address", None))
                if not bt_address:
                    continue

                devices_by_address[bt_address] = _merge_device(
                    devices_by_address.get(bt_address, {"bt_address": bt_address}),
                    {
                        "bt_address": bt_address,
                        "name": getattr(service_info, "name", None) or bt_address,
                        "rssi": getattr(service_info, "rssi", None),
                        "source": getattr(service_info, "source", None),
                        "connectable": getattr(service_info, "connectable", None),
                        "service_uuids": list(
                            getattr(service_info, "service_uuids", []) or []
                        ),
                        "manufacturer_data": dict(
                            getattr(service_info, "manufacturer_data", {}) or {}
                        ),
                        "service_data": dict(
                            getattr(service_info, "service_data", {}) or {}
                        ),
                    },
                )

        device_registry = dr.async_get(hass)
        for device_entry in device_registry.devices.values():
            for identifier in device_entry.identifiers:
                if identifier[0] == BLUETOOTH_DOMAIN:
                    bt_address = _normalize_address(str(identifier[1]))
                    devices_by_address[bt_address] = _merge_device(
                        devices_by_address.get(bt_address, {"bt_address": bt_address}),
                        {
                            "bt_address": bt_address,
                            "name": (
                                device_entry.name_by_user
                                or device_entry.name
                                or bt_address
                            ),
                            "model": device_entry.model,
                            "manufacturer": device_entry.manufacturer,
                            "device_id": device_entry.id,
                        },
                    )
                    break
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning("Could not enumerate Bluetooth devices: %s", err)

    devices = sorted(
        devices_by_address.values(),
        key=lambda item: (item.get("name") or item["bt_address"]).lower(),
    )
    _LOGGER.debug("Bluetooth devices found: %d", len(devices))
    return devices


async def async_get_bluetooth_device_active(
    hass: HomeAssistant, bt_address: str
) -> bool | None:
    """Return True when the Bluetooth address is currently present.

    This works for both registry-backed Bluetooth devices and scanner-only BLE
    devices that only exist in Home Assistant's Bluetooth discovery cache.
    """
    try:
        normalized = _normalize_address(bt_address)
        service_info = bluetooth.async_last_service_info(
            hass, normalized, connectable=False
        )
        if service_info is None:
            service_info = bluetooth.async_last_service_info(
                hass, normalized, connectable=True
            )
        if service_info is None:
            return None

        return bluetooth.async_address_present(hass, normalized, connectable=False)

    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Error checking Bluetooth device active status for '%s': %s",
            bt_address,
            err,
        )
        return None


async def async_get_bluetooth_device_details(
    hass: HomeAssistant, bt_address: str
) -> dict:
    """Return latest Bluetooth advertisement details for an address."""
    try:
        normalized = _normalize_address(bt_address)
        service_info = bluetooth.async_last_service_info(
            hass, normalized, connectable=False
        )
        if service_info is None:
            service_info = bluetooth.async_last_service_info(
                hass, normalized, connectable=True
            )
        if service_info is None:
            return {
                "active": False,
                "device_found": False,
            }

        return {
            "active": bluetooth.async_address_present(
                hass, normalized, connectable=False
            ),
            "device_found": True,
            "name": getattr(service_info, "name", None),
            "rssi": getattr(service_info, "rssi", None),
            "source": getattr(service_info, "source", None),
            "connectable": getattr(service_info, "connectable", None),
            "service_uuids": list(getattr(service_info, "service_uuids", []) or []),
            "manufacturer_data": dict(
                getattr(service_info, "manufacturer_data", {}) or {}
            ),
            "service_data": dict(getattr(service_info, "service_data", {}) or {}),
            "time": getattr(service_info, "time", None),
            "tx_power": getattr(service_info, "tx_power", None),
        }
    except (AttributeError, RuntimeError) as err:
        _LOGGER.warning(
            "Error getting Bluetooth device details for '%s': %s",
            bt_address,
            err,
        )
        return {
            "active": False,
            "device_found": False,
        }
