"""Support for Kindhome solarbeaker."""
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
)

from .const import DATA_DEVICE, DOMAIN, PLATFORMS, TITLE
from .kindhome_solarbeaker_ble import KindhomeSolarbeakerDevice
from .utils import log

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up battery sensor and kindhome cover from Kindhome solarbeaker config entry."""
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

    device = KindhomeSolarbeakerDevice(ble_device)

    log(_LOGGER, "async_setup_entry", f"successfully setup {device.device_name}")

    try:
        await device.connect()
        await device.get_state_and_subscribe_to_changes()

    except TimeoutError as e:
        _LOGGER.error(f"Error connecting to {device.ble_device}")
        # hass.components.persistent_notification.async_create(
        #     f"Connection error: error connecting to {device.ble_device}",
        #     title=TITLE,
        # )
        raise ConfigEntryNotReady(f"Error connecting to {device.ble_device}") from e

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_DEVICE: device}

    # Here I can create a task that tries to connect in a loop
    # homeassistant/components/velbus/__init__.py

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    log(_LOGGER, "async_unload_entry", "unloading entry!")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
