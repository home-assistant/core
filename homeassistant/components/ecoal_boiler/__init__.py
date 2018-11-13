"""
Support for ecoal/esterownik.pl coal/wood boiler controller.

Allows read various readings available in controller
and set very basic switches.
"""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecoal_boiler"

CONF_HOSTNAME = "host"
CONF_LOGIN = "login"
DEFAULT_LOGIN = "admin"
CONF_PASSWORD = "password"
DEFAULT_PASSWORD = "admin"


# CONFIG_SCHEMA = vol.Schema({
# DOMAIN: vol.Schema({
# vol.Required(CONF_HOSTNAME): cv.string,
# vol.Optional(CONF_LOGIN,
# default=DEFAULT_LOGIN): cv.string,
# vol.Optional(CONF_PASSWORD,
# default=DEFAULT_PASSWORD): cv.string,
# })
# })
# TODO: Fails with:
# [homeassistant.config] Invalid config for [ecoal_boiler]:
#       [homeassistant] is an invalid option for [ecoal_boiler].
#       Check: ecoal_boiler->homeassistant.
#  [homeassistant.setup] Setup failed for ecoal_boiler: Invalid config.


# CONFIG_SCHEMA = vol.Schema({
# DOMAIN: vol.Schema({
# })
# })

g_ecoal_contr = None

async def async_setup(hass, config):
    """Set up global g_ecoal_contr same for sensors and switches."""
    global g_ecoal_contr
    _LOGGER.debug("async_setup(): config: %r", config)
    from .http_iface import ECoalControler

    # hass.states.set('hello.world', 'Paulus')_LOGGE
    conf = config.get(DOMAIN)
    _LOGGER.debug(
        "async_setup(): conf: %r  conf.keys(): %r", conf, conf.keys()
    )

    host = conf.get(CONF_HOSTNAME)
    login = conf.get(CONF_LOGIN)
    passwd = conf.get(CONF_PASSWORD)
    _LOGGER.debug(
        "async_setup(): host: %r login: %r passwd: %r", host, login, passwd
    )
    g_ecoal_contr = ECoalControler(host, login, passwd)
    _LOGGER.debug("async_setup(): g_ecoal_contr: %r", g_ecoal_contr)

    return True
