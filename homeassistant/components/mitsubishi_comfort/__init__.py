"""Mitsubishi Comfort integration for Home Assistant."""

from __future__ import annotations

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


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Set up Mitsubishi Comfort from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = MitsubishiCloudAccount(username, password)
    if not await account.login():
        await account.close()
        raise ConfigEntryNotReady("Failed to authenticate with Mitsubishi cloud")

    try:
        cached: dict[str, dict] = entry.data.get("devices", {})
        devices = await account.discover_devices(cached_credentials=cached)
        if not devices:
            raise ConfigEntryNotReady("No devices discovered")

        # Persist credentials for next restart
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "devices": {
                    serial: {
                        "address": info.address,
                        "password": info.password,
                        "crypto_serial": info.crypto_serial,
                        "label": info.label,
                        "mac": info.mac,
                        "unit_type": info.unit_type,
                    }
                    for serial, info in devices.items()
                },
            },
        )

        coordinators: dict[str, MitsubishiComfortCoordinator] = {}
        for serial, info in devices.items():
            if not info.address or not info.password or not info.crypto_serial:
                _LOGGER.warning(
                    "Device %s missing credentials, skipping",
                    info.label,
                )
                continue
            device = _make_device(info, serial)
            coordinators[serial] = MitsubishiComfortCoordinator(hass, device)

        if not coordinators:
            raise ConfigEntryNotReady("No devices have complete credentials yet")

        entry.runtime_data = coordinators
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
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
