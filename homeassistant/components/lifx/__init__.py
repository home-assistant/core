"""Support for LIFX."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

CONF_SERVER = "server"
CONF_BROADCAST = "broadcast"

INTERFACE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_BROADCAST): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: {LIGHT_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [INTERFACE_SCHEMA]))}},
    extra=vol.ALLOW_EXTRA,
)

DATA_LIFX_MANAGER = "lifx_manager"


async def async_setup(hass, config):
    """Set up the LIFX component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up LIFX from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, LIGHT_DOMAIN)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.data.pop(DATA_LIFX_MANAGER).cleanup()

    await hass.config_entries.async_forward_entry_unload(entry, LIGHT_DOMAIN)

    return True
