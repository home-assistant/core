"""The Wyoming integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_SPEAKER, DOMAIN
from .data import WyomingService
from .devices import SatelliteDevice
from .models import DomainDataItem
from .websocket_api import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SATELLITE_PLATFORMS = [
    Platform.ASSIST_SATELLITE,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.NUMBER,
]

__all__ = [
    "ATTR_SPEAKER",
    "DOMAIN",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Wyoming integration."""
    async_register_websocket_api(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load Wyoming."""
    service = await WyomingService.create(entry.data["host"], entry.data["port"])

    if service is None:
        raise ConfigEntryNotReady("Unable to connect")

    item = DomainDataItem(service=service)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = item

    await hass.config_entries.async_forward_entry_setups(entry, service.platforms)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    if (satellite_info := service.info.satellite) is not None:
        # Create satellite device
        dev_reg = dr.async_get(hass)

        # Use config entry id since only one satellite per entry is supported
        satellite_id = entry.entry_id
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, satellite_id)},
            name=satellite_info.name,
            suggested_area=satellite_info.area,
        )

        item.device = SatelliteDevice(
            satellite_id=satellite_id,
            device_id=device.id,
        )

        # Set up satellite entity, sensors, switches, etc.
        await hass.config_entries.async_forward_entry_setups(entry, SATELLITE_PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wyoming."""
    item: DomainDataItem = hass.data[DOMAIN][entry.entry_id]

    platforms = list(item.service.platforms)
    if item.device is not None:
        platforms += SATELLITE_PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
