"""The Hisense AEH-W4A1 integration."""
<<<<<<< HEAD
import voluptuous as vol
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
import homeassistant.helpers.config_validation as cv
=======
>>>>>>> Isort and updated requirements_test_all.txt
=======
import ipaddress
>>>>>>> Implemented static ip addresses in configuration.yaml
=======
import ipaddress
import voluptuous as vol
>>>>>>> Corrected pylint wrong-import-order

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMA_DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


def coerce_ip(value):
    """Validate that provided value is a valid IP address."""
    if not value:
        raise vol.Invalid("Must define an IP address")
    try:
        ipaddress.IPv4Network(value)
    except ValueError:
        raise vol.Invalid("Not a valid IP address")
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            CLIMA_DOMAIN: vol.Schema(
                {
                    vol.Optional(CONF_IP_ADDRESS, default=[]): vol.Schema(
                        [vol.All(cv.string, coerce_ip)]
                    )
                }
            )
        }
    },
    extra=vol.ALLOW_EXTRA,
)
=======
=======
import homeassistant.helpers.config_validation as cv
>>>>>>> First working release, but there's a lot to do

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.components.climate import DOMAIN as CLIMA_DOMAIN
from .const import DOMAIN

INTERFACE_SCHEMA = vol.Schema({vol.Optional(CONF_IP_ADDRESS): cv.string})

<<<<<<< HEAD
CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}})
>>>>>>> First commit
=======
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: {CLIMA_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [INTERFACE_SCHEMA]))}},
    extra=vol.ALLOW_EXTRA,
)
>>>>>>> First working release, but there's a lot to do


async def async_setup(hass, config):
    """Set up the Hisense AEH-W4A1 integration."""
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> First working release, but there's a lot to do
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

<<<<<<< HEAD
=======
>>>>>>> First commit
=======
>>>>>>> First working release, but there's a lot to do
    return True


async def async_setup_entry(hass, entry):
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> First working release, but there's a lot to do
    """Set up a config entry for Hisense AEH-W4A1."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMA_DOMAIN)
    )
<<<<<<< HEAD

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
=======

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, CLIMA_DOMAIN)
>>>>>>> First working release, but there's a lot to do
