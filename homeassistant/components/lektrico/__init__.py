"""The Lektrico Charging Station integration."""
from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientSession
from lektricowifi import Device, DeviceConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CHARGERS_PLATFORMS, DOMAIN, LB_DEVICES_PLATFORMS
from .coordinator import LektricoDeviceDataUpdateCoordinator

PARALLEL_UPDATES = 1
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    session = async_get_clientsession(hass)

    try:
        coordinator = await create_coordinator(hass, entry, session)
    except DeviceConnectionError as lek_ex:
        raise ConfigEntryNotReady(lek_ex) from lek_ex

    await coordinator.async_config_entry_first_refresh()

    if coordinator.last_update_success is True:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        if coordinator.device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
            await hass.config_entries.async_forward_entry_setups(
                entry, CHARGERS_PLATFORMS
            )
        elif coordinator.device_type in (Device.TYPE_EM, Device.TYPE_3EM):
            await hass.config_entries.async_forward_entry_setups(
                entry, LB_DEVICES_PLATFORMS
            )
        else:
            # unknown type of device
            raise ConfigEntryError("Unsupported Lektrico device.")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, get_platforms(hass, entry)
    ):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def create_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, session: ClientSession
) -> LektricoDeviceDataUpdateCoordinator:
    """Create the coordinator for Lektrico Charging Station device."""
    coordinator = LektricoDeviceDataUpdateCoordinator(
        hass, entry.data[CONF_FRIENDLY_NAME], entry.data[CONF_HOST], session
    )
    await coordinator.get_config()
    return coordinator


def get_platforms(hass: HomeAssistant, entry: ConfigEntry) -> list[Platform]:
    """Return the platforms for this type of device."""
    _device_type: str = hass.data[DOMAIN][entry.entry_id].device_type
    if _device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        return CHARGERS_PLATFORMS
    return LB_DEVICES_PLATFORMS
