"""Sensor for Supervisord process status."""

from __future__ import annotations

import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_DESCRIPTION = "description"
ATTR_GROUP = "group"

DEFAULT_URL = "http://localhost:9001/RPC2"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_URL, default=DEFAULT_URL): cv.url}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Supervisord platform."""
    url = config[CONF_URL]
    try:
        supervisor_server = xmlrpc.client.ServerProxy(url)
        # See this link to explain the type ignore:
        # http://supervisord.org/api.html#supervisor.rpcinterface.SupervisorNamespaceRPCInterface.getAllProcessInfo
        processes: list[dict] = supervisor_server.supervisor.getAllProcessInfo()  # type: ignore[assignment]
    except ConnectionRefusedError:
        _LOGGER.error("Could not connect to Supervisord")
        return

    add_entities(
        [SupervisorProcessSensor(info, supervisor_server) for info in processes], True
    )


class SupervisorProcessSensor(SensorEntity):
    """Representation of a supervisor-monitored process."""

    def __init__(self, info, server):
        """Initialize the sensor."""
        self._info = info
        self._server = server
        self._available = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._info.get("name")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._info.get("statename")

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DESCRIPTION: self._info.get("description"),
            ATTR_GROUP: self._info.get("group"),
        }

    def update(self) -> None:
        """Update device state."""
        try:
            self._info = self._server.supervisor.getProcessInfo(
                self._info.get("group") + ":" + self._info.get("name")
            )
            self._available = True
        except ConnectionRefusedError:
            _LOGGER.warning("Supervisord not available")
            self._available = False
