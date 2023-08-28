"""The kindhome solarbeaker integration."""
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_COOR, DATA_DEVICE, DOMAIN, PLATFORMS, TITLE, UPDATE_INTERVAL
from .kindhome_solarbeaker_ble import KindhomeBluetoothDevice
from .utils import log

_LOGGER = logging.getLogger(__name__)

def create_async_update_method(device: KindhomeBluetoothDevice):
    # async def async_update_data() -> KindhomeSolarBeakerData:
    #     log(_LOGGER, "async_update_data", "polling for state!")
    #     async with async_timeout.timeout(10):
    #         data = await device.poll_data()
    #         return data
    #
    # return async_update_data

    # TODO should this task also reconnect?
    return None




async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    assert entry.entry_id is not None
    log(_LOGGER, "async_setup_entry", entry.data)

    ble_device = bluetooth.async_ble_device_from_address(hass, entry.data["address"])
    if ble_device is None:
        _LOGGER.error(f"Error creating BLE device for address {entry.data['address']}")
        hass.components.persistent_notification.async_create(
            f"Error creating BLE device for address {entry.data['address']}",
            title=TITLE,
        )
        raise ConfigEntryNotReady("Error creating ble device from address")

    device = KindhomeBluetoothDevice(ble_device)

    log(_LOGGER, "async_setup_entry", device.address)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="kindhome_solarbeaker",
        update_method=create_async_update_method(device),
        update_interval=UPDATE_INTERVAL,
    )

    # TODO do I want to use it?
    # await coordinator.async_config_entry_first_refresh()

    try:
        await device.connect()
    except TimeoutError:
        _LOGGER.error(f"Error connecting to {device.ble_device}")
        # hass.components.persistent_notification.async_create(
        #     f"Connection error: error connecting to {device.ble_device}",
        #     title=TITLE,
        # )
        raise ConfigEntryNotReady(f"Error connecting to {device.ble_device}")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_DEVICE: device, DATA_COOR: coordinator}


    # Here I can create a task that tries to connect in a loop
    # homeassistant/components/velbus/__init__.py


    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    log(_LOGGER, "async_unload_entry", "unloading entry!")

    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

