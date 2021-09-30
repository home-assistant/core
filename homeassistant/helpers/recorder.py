"""Helpers to check recorder."""


from homeassistant.core import HomeAssistant


async def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    if "recorder" not in hass.config.components:
        return False
    from homeassistant.components import (  # pylint: disable=import-outside-toplevel
        recorder,
    )

    return await recorder.async_migration_in_progress(hass)
