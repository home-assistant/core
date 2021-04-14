"""Helpers to check recorder."""
import logging

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


def wait_for_recorder_shutdown(hass: HomeAssistant) -> None:
    """Wait for recorder to shutdown."""
    if "recorder" not in hass.config.components:
        return
    from homeassistant.components.recorder.const import (  # pylint: disable=import-outside-toplevel
        DATA_INSTANCE,
    )

    instance = hass.data[DATA_INSTANCE]
    while True:
        instance.join(timeout=10)
        if not instance.is_alive():
            return
        _LOGGER.critical("Waiting for the recorder to safely shutdown")
