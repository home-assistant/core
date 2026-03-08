"""Integration for OpenDisplay BLE e-paper displays."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from opendisplay import (
    BLEConnectionError,
    BLETimeoutError,
    GlobalConfig,
    OpenDisplayDevice,
    OpenDisplayError,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.typing import ConfigType

if TYPE_CHECKING:
    from opendisplay.models import FirmwareVersion

from .const import DOMAIN
from .coordinator import OpenDisplayCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]


@dataclass
class OpenDisplayRuntimeData:
    """Runtime data for an OpenDisplay config entry."""

    coordinator: OpenDisplayCoordinator
    firmware: FirmwareVersion
    device_config: GlobalConfig
    is_flex: bool
    upload_task: asyncio.Task | None = None


type OpenDisplayConfigEntry = ConfigEntry[OpenDisplayRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenDisplay integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenDisplayConfigEntry) -> bool:
    """Set up OpenDisplay from a config entry."""
    address = entry.unique_id
    if TYPE_CHECKING:
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
            is_flex = device.is_flex
    except (BLEConnectionError, BLETimeoutError, OpenDisplayError) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to OpenDisplay device: {err}"
        ) from err
    device_config = device.config
    if TYPE_CHECKING:
        assert device_config is not None

    coordinator = OpenDisplayCoordinator(hass, address)

    manufacturer = device_config.manufacturer
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_BLUETOOTH, address)},
        name=entry.title,
        manufacturer=manufacturer.manufacturer_name,
        sw_version=f"{fw['major']}.{fw['minor']}",
        hw_version=(
            f"{manufacturer.board_type_name or manufacturer.board_type}"
            f" rev. {manufacturer.board_revision}"
        )
        if is_flex
        else None,
        configuration_url="https://opendisplay.org/firmware/config/"
        if is_flex
        else None,
    )

    entry.runtime_data = OpenDisplayRuntimeData(
        coordinator=coordinator,
        firmware=fw,
        device_config=device_config,
        is_flex=is_flex,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenDisplayConfigEntry
) -> bool:
    """Unload a config entry."""
    if (task := entry.runtime_data.upload_task) and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
