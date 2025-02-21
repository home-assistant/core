"""The meross_scan integration."""

from __future__ import annotations

from typing import Final

from meross_ha.controller.device import BaseDevice
from meross_ha.device import DeviceInfo
from meross_ha.device_manager import async_build_base_device
from meross_ha.exceptions import DeviceTimeoutError, InvalidMessage, MerossError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import _LOGGER
from .coordinator import MerossDataUpdateCoordinator

PLATFORMS: Final = [Platform.SENSOR, Platform.SWITCH]

MerossConfigEntry = ConfigEntry[MerossDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MerossConfigEntry
) -> bool:
    """Set up meross_scan from a config entry."""
    data = config_entry.data
    if not data.get(CONF_HOST) or not data.get("device"):
        raise ConfigEntryError("Invalid Host, please try again")
    try:
        device: DeviceInfo = DeviceInfo.from_dict(data["device"])
        base_device: BaseDevice = await async_build_base_device(device_info=device)
    except DeviceTimeoutError as err:
        raise ConfigEntryNotReady(f"Timed out connecting to {data[CONF_HOST]}") from err
    except InvalidMessage as err:
        raise ConfigEntryNotReady(f"Device data invalid {data[CONF_HOST]}") from err
    except MerossError as err:
        _LOGGER.debug(
            f"Device {config_entry.title} network connection failed, please check the network and try again"
        )
        raise ConfigEntryNotReady(repr(err)) from err

    coordinator = MerossDataUpdateCoordinator(hass, config_entry, base_device)
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MerossConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
