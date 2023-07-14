"""Backup platform for the ZHA integration."""
import logging

from homeassistant.core import HomeAssistant

from .core import ZHAGateway
from .core.const import DATA_ZHA, DATA_ZHA_GATEWAY

_LOGGER = logging.getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""
    _LOGGER.debug("Performing coordinator backup")

    zha_gateway: ZHAGateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    await zha_gateway.application_controller.backups.create_backup(load_devices=True)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
