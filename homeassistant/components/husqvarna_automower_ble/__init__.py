"""The Husqvarna Autoconnect Bluetooth integration."""

from __future__ import annotations

from automower_ble.mower import Mower
from automower_ble.protocol import ResponseResult
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address, get_device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, LOGGER
from .coordinator import HusqvarnaCoordinator

type HusqvarnaConfigEntry = ConfigEntry[HusqvarnaCoordinator]

PLATFORMS = [
    Platform.LAWN_MOWER,
    Platform.SENSOR,
]


async def async_migrate_entry(hass: HomeAssistant, entry: HusqvarnaConfigEntry) -> bool:
    """Migrate old entry."""

    LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        if entry.minor_version < 1:
            # Migrate from version 1.0 to 1.1
            new_data = entry.data.copy()
            new_data[CONF_ADDRESS] = format_mac(entry.data[CONF_ADDRESS])
            hass.config_entries.async_update_entry(
                entry, data=new_data, version=1, minor_version=1
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HusqvarnaConfigEntry) -> bool:
    """Set up Husqvarna Autoconnect Bluetooth from a config entry."""
    if CONF_PIN not in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="pin_required",
            translation_placeholders={"domain_name": "Husqvarna Automower BLE"},
        )

    address = entry.data[CONF_ADDRESS]
    pin = int(entry.data[CONF_PIN])
    channel_id = entry.data[CONF_CLIENT_ID]

    mower = Mower(channel_id, address, pin)

    await close_stale_connections_by_address(address)

    LOGGER.debug("connecting to %s with channel ID %s", address, str(channel_id))
    try:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        ) or await get_device(address)
        response_result = await mower.connect(device)
        if response_result == ResponseResult.INVALID_PIN:
            raise ConfigEntryAuthFailed(
                f"Unable to connect to device {address} due to wrong PIN"
            )
        if response_result != ResponseResult.OK:
            raise ConfigEntryNotReady(
                f"Unable to connect to device {address}, mower returned {response_result}"
            )
    except (TimeoutError, BleakError) as exception:
        raise ConfigEntryNotReady(
            f"Unable to connect to device {address} due to {exception}"
        ) from exception

    LOGGER.debug("connected and paired")

    model = await mower.get_model()
    LOGGER.debug("Connected to Automower: %s", model)

    coordinator = HusqvarnaCoordinator(hass, entry, mower, address, channel_id, model)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HusqvarnaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HusqvarnaCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
