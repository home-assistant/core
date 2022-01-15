"""Helpers to check recorder."""


from homeassistant.core import HomeAssistant


def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    if "recorder" not in hass.config.components:
        return False
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    return recorder.util.async_migration_in_progress(hass)
