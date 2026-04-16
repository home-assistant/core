"""Mitsubishi Comfort integration for Home Assistant."""

from __future__ import annotations

import logging

from mitsubishi_comfort import (
    DeviceInfo,
    IndoorUnit,
    KumoStation,
    MitsubishiCloudAccount,
)
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_RESPONSE_TIMEOUT, PLATFORMS
from .coordinator import MitsubishiComfortConfigEntry, MitsubishiComfortCoordinator

_LOGGER = logging.getLogger(__name__)


def _make_device(
    info: DeviceInfo,
    serial: str,
    session,
) -> IndoorUnit | KumoStation:
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
        session=session,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Set up Mitsubishi Comfort from a config entry."""
    session = async_get_clientsession(hass)
    account = MitsubishiCloudAccount(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
    )

    try:
        await account.login()
        devices = await account.discover_devices()
    except AuthenticationError as err:
        raise ConfigEntryError("Mitsubishi cloud authentication failed") from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady("Cannot reach Mitsubishi cloud") from err

    coordinators: dict[str, MitsubishiComfortCoordinator] = {}
    for serial, info in devices.items():
        if not info.address or not info.password or not info.crypto_serial:
            _LOGGER.warning("Device %s missing credentials, skipping", info.label)
            continue
        device = _make_device(info, serial, session)
        coordinators[serial] = MitsubishiComfortCoordinator(hass, entry, device)

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
