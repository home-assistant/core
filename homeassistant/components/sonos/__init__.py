"""Support to embed Sonos."""
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow


DOMAIN = 'sonos'


async def async_setup(hass, config):
    """Set up the Sonos component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up Sonos from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, 'media_player'))
    return True


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    import pysonos

    return await hass.async_add_executor_job(pysonos.discover)


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Sonos', _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH)
