"""The Husqvarna Autoconnect Bluetooth integration."""

from __future__ import annotations

from automower_ble.mower import Mower
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address, get_device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER
from .coordinator import HusqvarnaCoordinator

PLATFORMS = [
    Platform.LAWN_MOWER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Husqvarna Autoconnect Bluetooth from a config entry."""
    address = entry.data[CONF_ADDRESS]
    channel_id = entry.data[CONF_CLIENT_ID]

    mower = Mower(channel_id, address)

    await close_stale_connections_by_address(address)

    LOGGER.debug("connecting to %s with channel ID %s", address, str(channel_id))
    try:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        ) or await get_device(address)
        if not await mower.connect(device):
            raise ConfigEntryNotReady
    except (TimeoutError, BleakError) as exception:
        raise ConfigEntryNotReady(
            f"Unable to connect to device {address} due to {exception}"
        ) from exception
    LOGGER.debug("connected and paired")

    model = await mower.get_model()
    LOGGER.debug("Connected to Automower: %s", model)

    coordinator = HusqvarnaCoordinator(hass, mower, address, channel_id, model)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HusqvarnaCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
