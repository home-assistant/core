"""The Mammotion Luba integration."""
from __future__ import annotations


import logging

from pyluba.mammotion.devices import MammotionBaseBLEDevice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DEFAULT_RETRY_COUNT, CONF_RETRY_COUNT
from .coordinator import MammotionDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LAWN_MOWER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mammotion Luba from a config entry."""

    assert entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})
    if CONF_ADDRESS not in entry.data and CONF_MAC in entry.data:
        # Bleak uses addresses not mac addresses which are actually
        # UUIDs on some platforms (MacOS).
        mac = entry.data[CONF_MAC]
        if "-" not in mac:
            mac = dr.format_mac(mac)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ADDRESS: mac},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
        )

    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Mammotion lawn mower with address {address}"
        )

    device = MammotionBaseBLEDevice(ble_device)

    coordinator = hass.data[DOMAIN][entry.entry_id] = MammotionDataUpdateCoordinator(hass, _LOGGER, ble_device, device,
                                                                                     entry.unique_id,
                                                                                     entry.data.get(CONF_NAME,
                                                                                                    entry.title))

    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(f"{address} is not advertising state")

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
