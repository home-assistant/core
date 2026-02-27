"""Integration for OpenDisplay BLE e-paper displays."""

from __future__ import annotations

from opendisplay import (
    BLEConnectionError,
    BLETimeoutError,
    OpenDisplayDevice,
    OpenDisplayError,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, OpenDisplayConfigEntry, OpenDisplayRuntimeData
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenDisplay integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenDisplayConfigEntry) -> bool:
    """Set up OpenDisplay from a config entry."""
    address = entry.unique_id
    assert address is not None

    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Could not find OpenDisplay device with address {address}"
        )

    try:
        async with OpenDisplayDevice(
            mac_address=address, ble_device=ble_device
        ) as device:
            fw = await device.read_firmware_version()
            device_config = device.config
            assert device_config is not None
    except (BLEConnectionError, BLETimeoutError, OpenDisplayError) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to OpenDisplay device: {err}"
        ) from err

    entry.runtime_data = OpenDisplayRuntimeData(
        firmware=fw,
        device_config=device_config,
    )

    # Will be moved to DeviceInfo object in entity.py once entities are added
    manufacturer = device_config.manufacturer
    display = device_config.displays[0]
    board_type = manufacturer.board_type_name or str(manufacturer.board_type)
    color_scheme = getattr(display.color_scheme_enum, "name", str(display.color_scheme))
    size = (
        f'{display.screen_diagonal_inches:.1f}"'
        if display.screen_diagonal_inches is not None
        else f"{display.pixel_width}x{display.pixel_height}"
    )

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        connections={(CONNECTION_BLUETOOTH, address)},
        name=entry.title,
        manufacturer=manufacturer.manufacturer_name,
        model=f"{size} {color_scheme}",
        hw_version=f"{board_type} rev. {manufacturer.board_revision}",
        sw_version=f"{fw['major']}.{fw['minor']}",
        configuration_url="https://opendisplay.org/firmware/config/",
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenDisplayConfigEntry
) -> bool:
    """Unload a config entry."""
    return True
