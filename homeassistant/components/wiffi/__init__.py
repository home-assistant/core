"""Component for wiffi support."""

from datetime import timedelta
import errno
import logging

from wiffi import WiffiTcpServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import CHECK_ENTITIES_SIGNAL, CREATE_ENTITY_SIGNAL, UPDATE_ENTITY_SIGNAL
from .entity import generate_unique_id

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type WiffiConfigEntry = ConfigEntry[WiffiIntegrationApi]


async def async_setup_entry(hass: HomeAssistant, entry: WiffiConfigEntry) -> bool:
    """Set up wiffi from a config entry, config_entry contains data from config entry database."""

    # create api object
    api = WiffiIntegrationApi(hass)
    api.async_setup(entry)

    # store api object
    entry.runtime_data = api

    try:
        await api.server.start_server()
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            _LOGGER.error("Start_server failed, errno: %d", exc.errno)
            return False
        _LOGGER.error("Port %s already in use", entry.data[CONF_PORT])
        raise ConfigEntryNotReady from exc

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WiffiConfigEntry) -> bool:
    """Unload a config entry."""
    api = entry.runtime_data
    await api.server.close_server()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api.shutdown()

    return unload_ok


class WiffiIntegrationApi:
    """API object for wiffi handling."""

    def __init__(self, hass):
        """Initialize the instance."""
        self._hass = hass
        self._server = None
        self._known_devices = {}
        self._periodic_callback = None

    def async_setup(self, config_entry):
        """Set up api instance."""
        self._server = WiffiTcpServer(config_entry.data[CONF_PORT], self)
        self._periodic_callback = async_track_time_interval(
            self._hass, self._periodic_tick, timedelta(seconds=10)
        )

    def shutdown(self):
        """Shutdown wiffi api.

        Remove listener for periodic callbacks.
        """
        if (remove_listener := self._periodic_callback) is not None:
            remove_listener()

    async def __call__(self, device, metrics):
        """Process callback from TCP server if new data arrives from a device."""
        if device.mac_address not in self._known_devices:
            # add empty set for new device
            self._known_devices[device.mac_address] = set()

        for metric in metrics:
            if metric.id not in self._known_devices[device.mac_address]:
                self._known_devices[device.mac_address].add(metric.id)
                async_dispatcher_send(self._hass, CREATE_ENTITY_SIGNAL, device, metric)
            else:
                async_dispatcher_send(
                    self._hass,
                    f"{UPDATE_ENTITY_SIGNAL}-{generate_unique_id(device, metric)}",
                    device,
                    metric,
                )

    @property
    def server(self):
        """Return TCP server instance for start + close."""
        return self._server

    @callback
    def _periodic_tick(self, now=None):
        """Check if any entity has timed out because it has not been updated."""
        async_dispatcher_send(self._hass, CHECK_ENTITIES_SIGNAL)
