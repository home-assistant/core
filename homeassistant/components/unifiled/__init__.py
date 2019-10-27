"""Unifi LED Lights integration."""


async def async_setup(hass, config):
    """Set up the unifiled integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for unifiled."""

    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, "light"))

    return True
