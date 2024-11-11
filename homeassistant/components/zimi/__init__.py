"""The zcc integration."""

from __future__ import annotations

import logging

from zcc import ControlPoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import ZimiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to Zimi Controller and register device."""
    _LOGGER.debug("Zimi setup starting")

    coordinator = ZimiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    api: ControlPoint = coordinator.api
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, api.mac)},
        manufacturer=api.brand,
        name=f"Zimi({api.host}:{api.port})",
        model=api.product,
        model_id="Zimi Cloud Connect",
        hw_version=f"{api.mac}",
        sw_version=f"{api.firmware_version} (API {api.api_version})",
    )

    _LOGGER.debug("Zimi setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    api = entry.runtime_data
    api.disconnect()

    device_registry = dr.async_get(hass)

    zimi_device = device_registry.async_get_device(identifiers={(DOMAIN, api.mac)})

    assert zimi_device is not None

    device_registry.async_remove_device(device_id=zimi_device.id)

    return False
