"""Helpers to check recorder."""

import asyncio

from homeassistant.core import HomeAssistant, callback


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
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.recorder import const, models

    hass.data[const.DOMAIN] = models.RecorderData()


async def async_wait_recorder(hass: HomeAssistant) -> bool:
    """Wait for recorder to initialize and return connection status.

    Returns False immediately if the recorder is not enabled.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.recorder import const

    if const.DOMAIN not in hass.data:
        return False
    db_connected: asyncio.Future[bool] = hass.data[const.DOMAIN].db_connected
    return await db_connected
