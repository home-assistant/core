"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

from incomfortclient import Gateway as InComfortGateway

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import InComfortConfigEntry, InComfortData, InComfortDataCoordinator

PLATFORMS = (
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
)

INTEGRATION_TITLE = "Intergas InComfort/Intouch Lan2RF gateway"


@callback
def async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    data: InComfortData,
    gateway_device: dr.DeviceEntry,
) -> None:
    """Cleanup stale heater devices and climates."""
    heater_serial_numbers = {heater.serial_no for heater in data.heaters}
    device_registry = dr.async_get(hass)
    device_entries = device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    )
    stale_heater_serial_numbers: list[str] = [
        device_entry.serial_number
        for device_entry in device_entries
        if device_entry.id != gateway_device.id
        and device_entry.serial_number is not None
        and device_entry.serial_number not in heater_serial_numbers
    ]
    if not stale_heater_serial_numbers:
        return
    cleanup_devices: list[str] = []
    # Find stale heater and climate devices
    for serial_number in stale_heater_serial_numbers:
        cleanup_list = [f"{serial_number}_{index}" for index in range(1, 4)]
        cleanup_list.append(serial_number)
        cleanup_identifiers = [{(DOMAIN, cleanup_id)} for cleanup_id in cleanup_list]
        cleanup_devices.extend(
            device_entry.id
            for device_entry in device_entries
            if device_entry.identifiers in cleanup_identifiers
        )
    for device_id in cleanup_devices:
        device_registry.async_remove_device(device_id)


async def async_setup_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Set up a config entry."""

    credentials = dict(entry.data)
    hostname = credentials.pop(CONF_HOST)
    client = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )

    coordinator = InComfortDataCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
