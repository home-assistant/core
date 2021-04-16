"""Helpers to check recorder."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    if "recorder" not in hass.config.components:
        return False
    from homeassistant.components import (  # pylint: disable=import-outside-toplevel
        recorder,
    )

    return await recorder.async_migration_in_progress(hass)


async def async_wait_for_recorder_migration(hass: HomeAssistant) -> None:
    """Wait for recorder to shutdown after migration."""
    if not await async_migration_in_progress(hass):
        return
    from homeassistant.components.recorder.const import (  # pylint: disable=import-outside-toplevel
        DATA_INSTANCE,
    )

    instance = hass.data[DATA_INSTANCE]
    while True:
        if not instance.is_alive():
            return
        instance.join(timeout=10)
        _LOGGER.critical("Waiting for the recorder to safely shutdown")
