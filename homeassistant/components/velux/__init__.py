"""Support for VELUX KLF 200 devices."""
import logging

from pyvlx import PyVLX, PyVLXException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

DOMAIN = "velux"
DATA_VELUX = "data_velux"
PLATFORMS = ["cover", "scene"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Component setup, run import config flow for each entry in config."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Velux using config flow."""
    try:
        hass.data[DATA_VELUX] = VeluxModule(hass, config_entry)
        hass.data[DATA_VELUX].setup()
        await hass.data[DATA_VELUX].async_start()

    except PyVLXException as ex:
        _LOGGER.exception("Can't connect to velux interface: %s", ex)
        return False

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )
    return True


class VeluxModule:
    """Abstraction for velux component."""

    def __init__(self, hass: HomeAssistant, domain_config):
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

        async def async_reboot_gateway(service_call):
            await self.pyvlx.reboot_gateway()

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
        host = self._domain_config.data[CONF_HOST]
        password = self._domain_config.data[CONF_PASSWORD]
        self.pyvlx = PyVLX(host=host, password=password)

        self._hass.services.async_register(
            DOMAIN, "reboot_gateway", async_reboot_gateway
        )

    async def async_start(self):
        """Start velux component."""
        _LOGGER.debug("Velux interface started")
        await self.pyvlx.load_scenes()
        await self.pyvlx.load_nodes()
