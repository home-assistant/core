"""The Hisense AEH-W4A1 integration."""
import voluptuous as vol
<<<<<<< HEAD
import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.components.climate import DOMAIN as CLIMA_DOMAIN
from .const import DOMAIN

INTERFACE_SCHEMA = vol.Schema({vol.Optional(CONF_IP_ADDRESS): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: {CLIMA_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [INTERFACE_SCHEMA]))}},
    extra=vol.ALLOW_EXTRA,
)
=======

from .const import DOMAIN


CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}})
>>>>>>> First commit


async def async_setup(hass, config):
    """Set up the Hisense AEH-W4A1 integration."""
<<<<<<< HEAD
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

=======
>>>>>>> First commit
    return True


async def async_setup_entry(hass, entry):
<<<<<<< HEAD
    """Set up a config entry for Hisense AEH-W4A1."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMA_DOMAIN)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, CLIMA_DOMAIN)
=======
    """Set up a config entry for NEW_NAME."""
    # TODO forward the entry for each platform that you want to set up.
    # hass.async_create_task(
    #     hass.config_entries.async_forward_entry_setup(entry, "media_player")
    # )

    return True
>>>>>>> First commit
