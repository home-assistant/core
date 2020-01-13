"""Component for wiffi support."""
import asyncio
from datetime import timedelta
import errno
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .Wiffi import WiffiTcpServer
from .binary_sensor import BoolEntity
from .const import DOMAIN
from .sensor import NumberEntity, StringEntity

_LOGGER = logging.getLogger(__name__)

CONF_SERVERS = "servers"

SERVER_CONFIG = vol.Schema({vol.Required(CONF_PORT): cv.port}, extra=vol.ALLOW_EXTRA)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [SERVER_CONFIG])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


PLATFORMS = ["sensor", "binary_sensor"]


@callback
def configured_entries(hass):
    """Return a set contains the server ports of the configured wiffi integrations."""
    return set(
        entry.data[CONF_PORT] for entry in hass.config_entries.async_entries(DOMAIN)
    )


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the wiffi component. config contains data from configuration.yaml."""
    entries = configured_entries(hass)
    if DOMAIN in config:
        for server in config[DOMAIN][CONF_SERVERS]:
            port = server[CONF_PORT]
            if port not in entries:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data={CONF_PORT: port},
                    )
                )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up wiffi from a config entry, config_entry contains data from config entry database."""
    # create api object
    api = WiffiIntegrationApi(hass, config_entry)

    # store api object
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = api

    try:
        await api.server.start_server()
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        else:
            _LOGGER.error(f"port {config_entry.data[CONF_PORT]} already in use")
            raise ConfigEntryNotReady from e

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]  # type ::= WiffiIntegrationApi
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

    def __init__(self, hass, config_entry):
        """Initialize the instance."""
        self._hass = hass
        self._server = WiffiTcpServer(config_entry.data[CONF_PORT], self)
        self._known_devices = {}
        self._async_add_entities = {}
        self._periodic_callback = async_track_time_interval(
            hass, self._periodic_tick, timedelta(seconds=10)
        )

    def shutdown(self):
        """Shutdown wiffi api.

        Remove listener for periodic callbacks.
        """
        remove_listener = self._periodic_callback
        remove_listener()

    async def __call__(self, device, metrics):
        """Process callback from by TCP server if new data arives from a device."""
        if device.mac_address not in self._known_devices:
            # add all entities of new device
            self._known_devices[device.mac_address] = {}

            device_info = {
                "connections": {
                    (device_registry.CONNECTION_NETWORK_MAC, device.mac_address)
                },
                "identifiers": {(DOMAIN, device.mac_address)},
                "manufacturer": "stall.biz",
                "name": f"{device.moduletype} {device.mac_address}",
                "model": device.moduletype,
                "sw_version": device.sw_version,
            }

            sensor_entities = []
            bool_entities = []

            # unique entity id
            id = device.mac_address.replace(":", "")

            for metric in metrics:
                entity = None
                if metric.is_number:
                    entity = NumberEntity(id, device_info, metric)
                    sensor_entities.append(entity)
                elif metric.is_string:
                    entity = StringEntity(id, device_info, metric)
                    sensor_entities.append(entity)
                elif metric.is_bool:
                    entity = BoolEntity(id, device_info, metric)
                    bool_entities.append(entity)
                else:
                    # unknown type -> ignore
                    continue

                self._known_devices[device.mac_address][metric.id] = entity

            self._async_add_entities["sensor"](sensor_entities)
            self._async_add_entities["binary_sensor"](bool_entities)

        else:
            # update all entities
            for metric in metrics:
                entity = self._known_devices[device.mac_address].get(metric.id)
                if entity is not None:
                    await entity.update_value(metric)
                else:
                    _LOGGER.warning(
                        f"wiffi entity {device.mac_address}-{metric.id} not found"
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
                    entity.check_expiration_date()
