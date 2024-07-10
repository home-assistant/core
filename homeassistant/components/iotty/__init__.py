"""The iotty integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from iottycloud.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from . import coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]

type IottyConfigEntry = ConfigEntry[IottyConfigEntryData]


@dataclass
class IottyConfigEntryData:
    """Contains config entry data for iotty."""

    known_devices: set[Device]
    coordinator: coordinator.IottyDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: IottyConfigEntry) -> bool:
    """Set up iotty from a config entry."""
    _LOGGER.debug("async_setup_entry entry_id=%s", entry.entry_id)

    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    data_update_coordinator = coordinator.IottyDataUpdateCoordinator(
        hass, entry, session
    )

    entry.runtime_data = IottyConfigEntryData(set(), data_update_coordinator)

    await data_update_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
