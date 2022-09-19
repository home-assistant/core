"""The Snooz component."""
from __future__ import annotations

import logging

from pysnooz.advertisement import SnoozAdvertisementData
from pysnooz.device import SnoozDevice

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .models import SnoozConfigurationData

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snooz device from a config entry."""
    address = entry.data.get(CONF_ADDRESS)
    assert address

    token = entry.data.get(CONF_TOKEN)
    assert token

    if not (ble_device := async_ble_device_from_address(hass, address.upper())):
        raise ConfigEntryNotReady(
            f"Could not find Snooz with address {address}. Try power cycling the device"
        )

    data = SnoozAdvertisementData()
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
    )

    device = SnoozDevice(ble_device, token, hass.loop)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SnoozConfigurationData(
        ble_device, device, coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: SnoozConfigurationData = hass.data[DOMAIN][entry.entry_id]

        # also called by fan entities, but do it here too for good measure
        await data.device.async_disconnect()

        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok
