"""The Wyoming integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import ATTR_SPEAKER, DOMAIN
from .data import WyomingService
from .devices import SatelliteDevice
from .models import DomainDataItem
from .satellite import WyomingSatellite

_LOGGER = logging.getLogger(__name__)

SATELLITE_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.NUMBER,
]

__all__ = [
    "ATTR_SPEAKER",
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]


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
        # Create satellite device, etc.
        item.satellite = _make_satellite(hass, entry, service)

        # Set up satellite sensors, switches, etc.
        await hass.config_entries.async_forward_entry_setups(entry, SATELLITE_PLATFORMS)

        # Start satellite communication
        entry.async_create_background_task(
            hass,
            item.satellite.run(),
            f"Satellite {satellite_info.name}",
        )

        entry.async_on_unload(item.satellite.stop)

    return True


def _make_satellite(
    hass: HomeAssistant, config_entry: ConfigEntry, service: WyomingService
) -> WyomingSatellite:
    """Create Wyoming satellite/device from config entry and Wyoming service."""
    satellite_info = service.info.satellite
    assert satellite_info is not None

    dev_reg = dr.async_get(hass)

    # Use config entry id since only one satellite per entry is supported
    satellite_id = config_entry.entry_id

    device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, satellite_id)},
        name=satellite_info.name,
        suggested_area=satellite_info.area,
    )

    satellite_device = SatelliteDevice(
        satellite_id=satellite_id,
        device_id=device.id,
    )

    return WyomingSatellite(hass, service, satellite_device)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wyoming."""
    item: DomainDataItem = hass.data[DOMAIN][entry.entry_id]

    platforms = list(item.service.platforms)
    if item.satellite is not None:
        platforms += SATELLITE_PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
