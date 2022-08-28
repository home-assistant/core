"""Helpers to check recorder."""

import asyncio

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .models import RecorderData


def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    if "recorder" not in hass.config.components:
        return False
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    return recorder.util.async_migration_in_progress(hass)


@callback
def async_initialize_recorder(hass: HomeAssistant) -> None:
    """Initialize recorder data."""
    hass.data[DOMAIN] = RecorderData()


async def async_wait_recorder(hass: HomeAssistant) -> bool:
    """Wait for recorder to initialize and return connection status.

    Returns False immediately if the recorder is not enabled.
    """
    # pylint: disable-next=import-outside-toplevel
    if DOMAIN not in hass.data:
        return False
    db_connected: asyncio.Future[bool] = hass.data[DOMAIN].db_connected
    return await db_connected
