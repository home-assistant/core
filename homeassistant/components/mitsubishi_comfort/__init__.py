"""Mitsubishi Comfort integration for Home Assistant."""

from __future__ import annotations

import logging

from mitsubishi_comfort import (
    DeviceInfo,
    IndoorUnit,
    KumoStation,
    MitsubishiCloudAccount,
)

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_RESPONSE_TIMEOUT, PLATFORMS
from .coordinator import MitsubishiComfortConfigEntry, MitsubishiComfortCoordinator

_LOGGER = logging.getLogger(__name__)


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
    account = MitsubishiCloudAccount(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )

    try:
        login_ok = await account.login()
    except Exception as err:
        await account.close()
        raise ConfigEntryNotReady("Failed to connect to Mitsubishi cloud") from err

    if not login_ok:
        await account.close()
        raise ConfigEntryNotReady("Failed to authenticate with Mitsubishi cloud")

    try:
        devices = await account.discover_devices()
    except Exception as err:
        await account.close()
        raise ConfigEntryNotReady("Failed to discover devices") from err
    finally:
        await account.close()

    if not devices:
        raise ConfigEntryNotReady("No devices discovered")

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


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for coordinator in entry.runtime_data.values():
            await coordinator.device.close()
    return unload_ok
