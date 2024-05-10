"""The Zimi integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to Zimi Controller and register device."""

    _LOGGER.debug("Zimi setup starting")

    controller = ZimiController(hass, entry)
    connected = await controller.connect()
    if not connected:
        return False

    hass.data[CONTROLLER] = controller

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.controller.mac)},
        manufacturer=controller.controller.brand,
        name=f"Zimi({controller.controller.host}:{controller.controller.port})",
        model=controller.controller.product,
        sw_version="unknown",
    )

    _LOGGER.debug("Zimi setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Zimi entry and clean up opened connections."""

    _LOGGER.info("Unloading Zimi Controller")

    _LOGGER.debug("async_unload_entry()")
    _LOGGER.debug("entry_id: %s", entry.entry_id)

    controller = ZimiController(hass, entry)
    await controller.disconnect()

    device_registry = dr.async_get(hass)
    device_registry.async_remove_device(entry.entry_id)

    return True
