"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

from aiohttp import ClientResponseError
from incomfortclient import InvalidGateway, InvalidHeaterList

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import (
    InComfortConfigEntry,
    InComfortData,
    InComfortDataCoordinator,
    async_connect_gateway,
)
from .errors import InComfortTimeout, InComfortUnknownError, NoHeaters, NotFound

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
    try:
        data = await async_connect_gateway(hass, dict(entry.data))
        for heater in data.heaters:
            await heater.update()
    except InvalidHeaterList as exc:
        raise NoHeaters from exc
    except InvalidGateway as exc:
        raise ConfigEntryAuthFailed("Incorrect credentials") from exc
    except ClientResponseError as exc:
        if exc.status == 404:
            raise NotFound from exc
        raise InComfortUnknownError from exc
    except TimeoutError as exc:
        raise InComfortTimeout from exc

    # Register discovered gateway device
    device_registry = dr.async_get(hass)
    gateway_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
        if entry.unique_id is not None
        else set(),
        manufacturer="Intergas",
        name="RFGateway",
    )
    async_cleanup_stale_devices(hass, entry, data, gateway_device)
    coordinator = InComfortDataCoordinator(hass, entry, data)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
