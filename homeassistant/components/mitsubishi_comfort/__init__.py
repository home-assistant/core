"""Mitsubishi Comfort integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging

from mitsubishi_comfort import (
    DeviceInfo,
    IndoorUnit,
    KumoStation,
    MitsubishiCloudAccount,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_RESPONSE_TIMEOUT, PLATFORMS
from .coordinator import MitsubishiComfortCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_DEVICES = "devices"

type MitsubishiComfortConfigEntry = ConfigEntry[dict[str, MitsubishiComfortCoordinator]]


def _make_device(info: DeviceInfo, serial: str) -> IndoorUnit | KumoStation:
    """Create the appropriate device instance from DeviceInfo."""
    cls = IndoorUnit if info.is_indoor_unit else KumoStation
    return cls(
        name=info.label,
        address=info.address,
        password_b64=info.password,
        crypto_serial_hex=info.crypto_serial,
        serial=serial,
        connect_timeout=DEFAULT_CONNECT_TIMEOUT,
        response_timeout=DEFAULT_RESPONSE_TIMEOUT,
    )


def _devices_to_cache(devices: dict[str, DeviceInfo]) -> dict[str, dict]:
    """Serialize device credentials for storage in config entry data."""
    return {
        serial: {
            "address": info.address,
            "password": info.password,
            "crypto_serial": info.crypto_serial,
            "label": info.label,
            "mac": info.mac,
            "unit_type": info.unit_type,
        }
        for serial, info in devices.items()
    }


def _merge_cached_into_devices(
    devices: dict[str, DeviceInfo], cached: dict[str, dict]
) -> list[str]:
    """Merge cached credentials into discovered devices."""
    updated = []
    for serial, info in devices.items():
        if serial not in cached:
            continue
        c = cached[serial]
        if not info.address and c.get("address"):
            info.address = c["address"]
        if not info.password and c.get("password"):
            info.password = c["password"]
            updated.append(serial)
        if not info.crypto_serial and c.get("crypto_serial"):
            info.crypto_serial = c["crypto_serial"]
    return updated


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Set up Mitsubishi Comfort from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = MitsubishiCloudAccount(username, password)
    account_handed_off = False
    try:
        if not await account.login():
            raise ConfigEntryNotReady("Failed to authenticate with Mitsubishi cloud")

        cached: dict[str, dict] = entry.data.get(CONF_DEVICES, {})

        devices = await account.discover_devices(cached_credentials=cached)
        if not devices:
            raise ConfigEntryNotReady("No devices discovered")

        updated = _merge_cached_into_devices(devices, cached)
        if updated:
            _LOGGER.info(
                "Restored cached credentials for: %s",
                ", ".join(devices[s].label for s in updated),
            )

        # Persist credentials in config entry for next restart
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DEVICES: _devices_to_cache(devices)},
        )

        coordinators: dict[str, MitsubishiComfortCoordinator] = {}
        incomplete_serials: list[str] = []
        for serial, info in devices.items():
            if not info.address or not info.password or not info.crypto_serial:
                incomplete_serials.append(serial)
                _LOGGER.warning(
                    "Device %s missing credentials (addr=%s, pw=%s, crypto=%s)"
                    " — will retry in background",
                    info.label,
                    bool(info.address),
                    bool(info.password),
                    bool(info.crypto_serial),
                )
                continue

            device = _make_device(info, serial)
            coordinators[serial] = MitsubishiComfortCoordinator(hass, device)

        if not coordinators:
            raise ConfigEntryNotReady("No devices have complete credentials yet")

        entry.runtime_data = coordinators

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        if incomplete_serials:
            account_handed_off = True
            hass.async_create_task(
                _retry_incomplete_devices(
                    hass,
                    entry,
                    account,
                    devices,
                    incomplete_serials,
                )
            )

        return True
    finally:
        if not account_handed_off:
            await account.close()


async def _retry_incomplete_devices(
    hass: HomeAssistant,
    entry: MitsubishiComfortConfigEntry,
    account: MitsubishiCloudAccount,
    devices: dict[str, DeviceInfo],
    incomplete_serials: list[str],
) -> None:
    """Retry credential retrieval for devices that were missing passwords."""
    try:
        for attempt in range(3):
            await asyncio.sleep(30 * (attempt + 1))

            if not hasattr(entry, "runtime_data"):
                return

            _LOGGER.info(
                "Background retry %d/3 for %d incomplete devices",
                attempt + 1,
                len(incomplete_serials),
            )

            passwords = await account.get_passwords_via_websocket(
                incomplete_serials, timeout_secs=60
            )

            newly_complete = []
            for serial in list(incomplete_serials):
                info = devices[serial]
                if serial in passwords and not info.password:
                    info.password = passwords[serial]
                if info.address and info.password and info.crypto_serial:
                    newly_complete.append(serial)

            if not newly_complete:
                continue

            coordinators = entry.runtime_data
            for serial in newly_complete:
                info = devices[serial]
                incomplete_serials.remove(serial)
                _LOGGER.info("Device %s now has complete credentials", info.label)
                device = _make_device(info, serial)
                coordinators[serial] = MitsubishiComfortCoordinator(hass, device)

            # Persist updated credentials
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_DEVICES: _devices_to_cache(devices)},
            )
            await hass.config_entries.async_reload(entry.entry_id)
            return

        if incomplete_serials:
            _LOGGER.warning(
                "Could not retrieve credentials for: %s — restart to retry",
                ", ".join(devices[s].label for s in incomplete_serials),
            )
    finally:
        await account.close()


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for coordinator in entry.runtime_data.values():
            await coordinator.device.close()
    return unload_ok
