"""Support to embed Sonos."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_HOSTS
from homeassistant.helpers import config_entry_flow, config_validation as cv

DOMAIN = 'sonos'

CONF_ADVERTISE_ADDR = 'advertise_addr'
CONF_INTERFACE_ADDR = 'interface_addr'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        MP_DOMAIN: vol.Schema({
            vol.Optional(CONF_ADVERTISE_ADDR): cv.string,
            vol.Optional(CONF_INTERFACE_ADDR): cv.string,
            vol.Optional(CONF_HOSTS): vol.All(cv.ensure_list_csv, [cv.string]),
        }),
    }),
}, extra=vol.ALLOW_EXTRA)


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
        entry, MP_DOMAIN))
    return True


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    import pysonos

    return await hass.async_add_executor_job(pysonos.discover)


config_entry_flow.register_discovery_flow(
    DOMAIN, 'Sonos', _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH)
