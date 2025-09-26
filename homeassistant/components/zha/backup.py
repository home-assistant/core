"""Backup platform for the ZHA integration."""

import logging

from homeassistant.core import HomeAssistant

from .helpers import get_zha_gateway

_LOGGER = logging.getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""
    _LOGGER.debug("Performing coordinator backup")

    try:
        zha_gateway = get_zha_gateway(hass)
    except ValueError:
        # If ZHA config is in `configuration.yaml` and ZHA is not set up, do nothing
        _LOGGER.warning("No ZHA gateway exists, skipping coordinator backup")
        return

    await zha_gateway.application_controller.backups.create_backup(load_devices=True)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
