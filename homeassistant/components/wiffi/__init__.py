"""Component for wiffi support."""
import asyncio
from datetime import timedelta
import errno
import logging

from wiffi import WiffiTcpServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import CREATE_ENTITY_SIGNAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the wiffi component. config contains data from configuration.yaml."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up wiffi from a config entry, config_entry contains data from config entry database."""
    # create api object
    api = WiffiIntegrationApi(hass)
    api.setup(config_entry)

    # store api object
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = api

    try:
        await api.server.start_server()
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            _LOGGER.error(f"start_server failed, errno: {exc.errno}")
            return False
        _LOGGER.error("port %s already in use", config_entry.data[CONF_PORT])
        raise ConfigEntryNotReady from exc

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    api: "WiffiIntegrationApi" = hass.data[DOMAIN][config_entry.entry_id]
    await api.server.close_server()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        api = hass.data[DOMAIN].pop(config_entry.entry_id)
        api.shutdown()

    return unload_ok


class WiffiIntegrationApi:
    """API object for wiffi handling. Stored in hass.data."""

    def __init__(self, hass):
        """Initialize the instance."""
        self._hass = hass
        self._server = None
        self._known_devices = {}
        self._async_add_entities = {}
        self._periodic_callback = None

    def setup(self, config_entry):
        """Set up api instance."""
        self._server = WiffiTcpServer(config_entry.data[CONF_PORT], self)
        self._periodic_callback = async_track_time_interval(
            self._hass, self._periodic_tick, timedelta(seconds=10)
        )

    def shutdown(self):
        """Shutdown wiffi api.

        Remove listener for periodic callbacks.
        """
        remove_listener = self._periodic_callback
        if remove_listener is not None:
            remove_listener()

    async def __call__(self, device, metrics):
        """Process callback from TCP server if new data arrives from a device."""
        if device.mac_address not in self._known_devices:
            # add all entities of new device
            self._known_devices[device.mac_address] = {}

            async_dispatcher_send(
                self._hass, CREATE_ENTITY_SIGNAL, self, device, metrics
            )

        else:
            # update all entities
            for metric in metrics:
                entity = self._known_devices[device.mac_address].get(metric.id)
                if entity is not None:
                    await entity.update_value(metric)
                else:
                    _LOGGER.warning(
                        "wiffi entity %s-%s not found", device.mac_address, metric.id
                    )

    @property
    def server(self):
        """Return TCP server instance for start + close."""
        return self._server

    @property
    def async_add_entities(self):
        """Return dict with add_entities functions for every platform."""
        return self._async_add_entities

    @callback
    def _periodic_tick(self, now=None):
        """Check if any entity has timed out because it has not been updated."""
        for entities in self._known_devices.values():
            for entity in entities.values():
                if entity is not None:
                    entity.async_check_expiration_date()

    def add_entity(self, mac_address, metric_id, entity):
        """Add entity to list of known entities."""
        self._known_devices[mac_address][metric_id] = entity
