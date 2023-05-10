"""The BeeWi SmartClim component."""

from __future__ import annotations

import logging

from smartclim_ble import BeeWiSmartClimAdvertisement

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def _service_info_to_adv(
    service_info: BluetoothServiceInfoBleak,
) -> BeeWiSmartClimAdvertisement:
    return BeeWiSmartClimAdvertisement(service_info.device, service_info.advertisement)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BeeWi SmartClim BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=_service_info_to_adv,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        # only start after all platforms have had a chance to subscribe
        coordinator.async_start()
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
