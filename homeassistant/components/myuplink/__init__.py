"""The myUplink integration."""
from __future__ import annotations

from myuplink.api import MyUplinkAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)

from . import api
from .const import (
    DOMAIN,
    MU_DATAGROUP_DEVICES,
    MU_DEVICE_FIRMWARE_CURRENT,
    MU_DEVICE_PRODUCTNAME,
)
from .coordinator import MyUplinkDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up myUplink from a config entry."""

    hass.data[DOMAIN] = {}

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, config_entry, implementation)

    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    # Setup MyUplinkAPI and coordinator for data fetch
    mu_api = MyUplinkAPI(auth)
    mu_coordinator = MyUplinkDataCoordinator(hass, mu_api)

    await mu_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = {
        "api": mu_api,
        "coordinator": mu_coordinator,
    }

    # Update device registry
    await update_all_devices(hass, config_entry, mu_coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_all_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: MyUplinkDataCoordinator
):
    """Update all devices."""
    mu_devices = coordinator.data[MU_DATAGROUP_DEVICES]

    device_registry = dr.async_get(hass)

    for device_id in mu_devices:
        device_data = mu_devices[device_id]

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            name=device_data[MU_DEVICE_PRODUCTNAME],
            manufacturer=device_data[MU_DEVICE_PRODUCTNAME].split(" ")[0],
            model=device_data[MU_DEVICE_PRODUCTNAME],
            sw_version=device_data[MU_DEVICE_FIRMWARE_CURRENT],
        )
