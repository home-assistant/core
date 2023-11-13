"""The fever_smart integration."""
from __future__ import annotations
import logging

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import bluetooth

from .fever_smart import FeverSmartParser

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.SENSOR]
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fever_smart from a config entry."""
    # hass.data.setdefault(DOMAIN, {})
    # # TODO 1. Create API instance
    # # TODO 2. Validate the API connection (and authentication)
    # # TODO 3. Store an API object for your platforms to access
    # # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # service_infos = bluetooth.async_discovered_service_info(hass, connectable=True)
    # for si in service_infos:
    #     _LOGGER.warning("New service_info: %s", si)

    # entry.async_on_unload(
    #     bluetooth.async_register_callback(
    #         hass,
    #         _async_discovered_device,
    #         {
    #             "service_uuid": "00001809-0000-1000-8000-00805f9b34fb",
    #             "connectable": False,
    #         },
    #         bluetooth.BluetoothScanningMode.ACTIVE,
    #     )
    # )

    # Copied

    address = entry.unique_id
    data = FeverSmartParser()
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
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
