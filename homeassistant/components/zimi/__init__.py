"""The zcc integration."""
from __future__ import annotations

import logging
import pprint

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONTROLLER, DOMAIN, VERBOSITY
from .controller import ZimiController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to Zimi Controller and register device."""

    _LOGGER.info("Setting up Zimi Controller")

    if entry.data.get(VERBOSITY, 0) > 1:
        _LOGGER.setLevel(logging.DEBUG)

    _LOGGER.debug("async_setup_entry()")
    _LOGGER.debug("entry_id: %s", entry.entry_id)
    _LOGGER.debug("data: %s", pprint.pformat(entry.data))

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

    return True
