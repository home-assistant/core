"""The Pinecil integration."""

from __future__ import annotations

import logging

from bleak import BleakClient
from pinecil import BLE, Pinecil

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import PinecilCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR]

type PinecilConfigEntry = ConfigEntry[PinecilCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PinecilConfigEntry) -> bool:
    """Set up Pinecil from a config entry."""

    #
    class _BLE(BLE):
        """BLE device wrapper."""

        def __init__(self, address: str) -> None:  # pylint: disable=W0231
            """BLE device wrapper."""
            self.__address = address
            self.__client = BleakClient(  # pylint: disable=W0238
                self.__address, disconnected_callback=self.__on_disconnected
            )

        def __on_disconnected(self, client: BleakClient) -> None:  # pylint: disable=W0238
            """Device disconnect callback."""
            _LOGGER.debug("Disconnected from Pinecil device %s", self.__address)

    pinecil = Pinecil(_BLE(entry.data[CONF_ADDRESS]))

    coordinator = PinecilCoordinator(hass, pinecil)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PinecilConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
