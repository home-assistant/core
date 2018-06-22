"""Component to embed Google Cast."""
from homeassistant.helpers import config_entry_flow


DOMAIN = 'cast'
REQUIREMENTS = ['pychromecast==2.1.0']


async def async_setup(hass, config):
    """Set up the Cast component."""
    hass.data[DOMAIN] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
    """Set up Cast from a config entry."""
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(
        entry, 'media_player'))
    return True


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    from pychromecast.discovery import discover_chromecasts

    return await hass.async_add_job(discover_chromecasts)


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Google Cast', _async_has_devices)
