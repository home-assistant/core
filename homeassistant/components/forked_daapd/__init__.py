"""The forked_daapd component."""

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN


async def async_setup(hass, config):
    """Set up the forked-daapd component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up forked-daapd from a config entry by forwarding to platform."""
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN))
    return True


async def async_unload_entry(hass, entry):
    """Remove forked-daapd component."""
    await hass.config_entries.async_forward_entry_unload(entry, MP_DOMAIN)
    return True
