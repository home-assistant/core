"""Backup platform for the ZHA integration."""

import logging

from homeassistant.core import HomeAssistant

from .core.helpers import get_zha_gateway

_LOGGER = logging.getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""
    _LOGGER.debug("Performing coordinator backup")

    zha_gateway = get_zha_gateway(hass)
    await zha_gateway.application_controller.backups.create_backup(load_devices=True)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
