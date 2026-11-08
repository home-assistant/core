"""The Powerfox integration."""

import asyncio

from powerfox import DeviceType, Powerfox

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import (
    PowerfoxConfigEntry,
    PowerfoxCoordinator,
    PowerfoxDataUpdateCoordinator,
    PowerfoxDeviceListCoordinator,
    PowerfoxReportDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PowerfoxConfigEntry) -> None:
    """Set up Powerfox from a config entry."""
    client = Powerfox(
        username=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    device_list_coordinator = PowerfoxDeviceListCoordinator(hass, entry, client)
    await device_list_coordinator.async_config_entry_first_refresh()

    device_ids = {device.id for device in device_list_coordinator.data}
    _async_remove_stale_devices(hass, entry, device_ids)

    coordinators: list[PowerfoxCoordinator] = []
    for device in device_list_coordinator.data:
        if device.type == DeviceType.GAS_METER:
            coordinators.append(
                PowerfoxReportDataUpdateCoordinator(hass, entry, client, device)
            )
            continue
        coordinators.append(PowerfoxDataUpdateCoordinator(hass, entry, client, device))

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_reload_on_device_change() -> None:
        """Reload the entry when the devices of the account have changed."""
        if {device.id for device in device_list_coordinator.data} != device_ids:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        device_list_coordinator.async_add_listener(_async_reload_on_device_change)
    )


async def async_unload_entry(hass: HomeAssistant, entry: PowerfoxConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


@callback
def _async_remove_stale_devices(
    hass: HomeAssistant, entry: PowerfoxConfigEntry, device_ids: set[str]
) -> None:
    """Remove devices that are no longer part of the Powerfox account."""
    known_identifiers = {(DOMAIN, device_id) for device_id in device_ids}
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if device_entry.identifiers.isdisjoint(known_identifiers):
            device_registry.async_remove_device(device_entry.id)
