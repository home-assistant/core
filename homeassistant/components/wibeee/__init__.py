"""The Wibeee integration."""

from dataclasses import dataclass

import aiohttp
from pywibeee import WibeeeAPI, WibeeeDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_MAC_ADDRESS, CONF_WIBEEE_ID
from .coordinator import WibeeeCoordinator

PLATFORMS = [Platform.SENSOR]


@dataclass
class WibeeeRuntimeData:
    """Runtime data stored in entry.runtime_data."""

    api: WibeeeAPI
    device_info: WibeeeDeviceInfo
    coordinator: WibeeeCoordinator


type WibeeeConfigEntry = ConfigEntry[WibeeeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WibeeeConfigEntry) -> bool:
    """Set up Wibeee from a config entry."""
    host = entry.data[CONF_HOST]
    mac_addr = entry.data[CONF_MAC_ADDRESS]
    wibeee_id = entry.data.get(CONF_WIBEEE_ID, "WIBEEE")

    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, host)

    try:
        device_info = await api.async_fetch_device_info(retries=3)
    except (TimeoutError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady(f"Could not connect to Wibeee at {host}") from err

    if device_info is None:
        device_info = WibeeeDeviceInfo(
            wibeee_id=wibeee_id,
            mac_addr=mac_addr,
            model="Unknown",
            firmware_version="Unknown",
            ip_addr=host,
        )

    coordinator = WibeeeCoordinator(
        hass,
        api,
        config_entry=entry,
        name=f"Wibeee {device_info.mac_addr_short}",
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WibeeeRuntimeData(
        api=api, device_info=device_info, coordinator=coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WibeeeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
