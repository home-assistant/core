"""The Refoss RPC integration."""

from __future__ import annotations

from typing import Final

from aiorefoss.common import ConnectionOptions
from aiorefoss.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
)
from aiorefoss.rpc_device import RpcDevice

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import RefossConfigEntry, RefossCoordinator, RefossEntryData

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: RefossConfigEntry) -> bool:
    """Set up Refoss RPC from a config entry."""
    if not entry.data.get(CONF_HOST):
        raise ConfigEntryError("Invalid Host, please try again")

    options = ConnectionOptions(
        entry.data.get(CONF_HOST),
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        entry.data.get(CONF_MAC),
    )

    device = await RpcDevice.create(
        async_get_clientsession(hass),
        options,
    )
    runtime_data = entry.runtime_data = RefossEntryData(PLATFORMS)

    try:
        await device.initialize()
    except (DeviceConnectionError, MacAddressMismatchError) as err:
        await device.shutdown()
        raise ConfigEntryNotReady(repr(err)) from err
    except InvalidAuthError as err:
        await device.shutdown()
        raise ConfigEntryAuthFailed(repr(err)) from err

    runtime_data.coordinator = RefossCoordinator(hass, entry, device)
    runtime_data.coordinator.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, runtime_data.platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RefossConfigEntry) -> bool:
    """Unload a config entry."""

    runtime_data = entry.runtime_data

    if runtime_data.coordinator:
        await runtime_data.coordinator.shutdown()

    return await hass.config_entries.async_unload_platforms(
        entry, runtime_data.platforms
    )
