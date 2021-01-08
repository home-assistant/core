"""Support for VELUX KLF 200 devices."""
import logging

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

DOMAIN = "velux"
DATA_VELUX = "data_velux"
SUPPORTED_DOMAINS = ["cover", "scene"]
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PASSWORD): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the velux component."""
    try:
        hass.data[DATA_VELUX] = VeluxModule(hass, config[DOMAIN])
        hass.data[DATA_VELUX].setup()
        await hass.data[DATA_VELUX].async_start()

    except PyVLXException as ex:
        _LOGGER.exception("Can't connect to velux interface: %s", ex)
        return False

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config)
        )
    return True


class VeluxModule:
    """Abstraction for velux component."""

    def __init__(self, hass, domain_config):
        """Initialize for velux component."""
        self.pyvlx = None
        self._hass = hass
        self._domain_config = domain_config

    def setup(self):
        """Velux component setup."""

        async def on_hass_stop(event):
            """Close connection when hass stops."""
            _LOGGER.debug("Velux interface terminated")
            await self.pyvlx.disconnect()

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
        host = self._domain_config.get(CONF_HOST)
        password = self._domain_config.get(CONF_PASSWORD)
        self.pyvlx = PyVLX(host=host, password=password)

    async def async_start(self):
        """Start velux component."""
        _LOGGER.debug("Velux interface started")
        await self.pyvlx.load_scenes()
        await self.pyvlx.load_nodes()
