"""Support for VELUX KLF 200 devices."""

from pyvlx import PyVLX, PyVLXException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the velux component."""
    module = VeluxModule(hass, entry.data)
    try:
        module.setup()
        await module.async_start()

    except PyVLXException as ex:
        LOGGER.exception("Can't connect to velux interface: %s", ex)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = module

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
            LOGGER.debug("Velux interface terminated")
            await self.pyvlx.disconnect()

        async def async_reboot_gateway(service_call: ServiceCall) -> None:
            await self.pyvlx.reboot_gateway()

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
        host = self._domain_config.get(CONF_HOST)
        password = self._domain_config.get(CONF_PASSWORD)
        self.pyvlx = PyVLX(host=host, password=password)

        self._hass.services.async_register(
            DOMAIN, "reboot_gateway", async_reboot_gateway
        )

    async def async_start(self):
        """Start velux component."""
        LOGGER.debug("Velux interface started")
        await self.pyvlx.load_scenes()
        await self.pyvlx.load_nodes()
