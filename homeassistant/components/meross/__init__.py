"""The Meross Bluetooth integration."""

from meross_ble import DEFAULT_RETRY_COUNT, MerossModel, create_device

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import MerossBLEDataUpdateCoordinator, MerossConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Set up one Meross BLE device from a config entry."""
    assert entry.unique_id is not None
    address: str = entry.data[CONF_ADDRESS]
    model = MerossModel(entry.data[CONF_MODEL])
    # False accepts connectable and non-connectable advertisements (common on macOS).
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=False
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Meross BLE device with address {address}"
        )

    device = create_device(ble_device, model, retry_count=DEFAULT_RETRY_COUNT)
    coordinator = entry.runtime_data = MerossBLEDataUpdateCoordinator(
        hass,
        entry,
        ble_device,
        device,
    )
    device.bind_runtime(
        refresh_ble_device=lambda: bluetooth.async_ble_device_from_address(
            hass, address.upper(), True
        ),
        wait_advertisement=coordinator.async_wait_next_advertisement,
        last_service_info=lambda: bluetooth.async_last_service_info(
            hass, address, connectable=False
        ),
    )
    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(
            f"Meross BLE device {address} not advertising yet; will retry"
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Unload a Meross BLE config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
