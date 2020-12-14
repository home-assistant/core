"""Support for Plex media server monitoring."""
import logging

from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    NAME_FORMAT,
    PLEX_UPDATE_SENSOR_SIGNAL,
    SERVERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plex sensor from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    plexserver = hass.data[PLEX_DOMAIN][SERVERS][server_id]
    sensor = PlexSensor(hass, plexserver)
    async_add_entities([sensor])


class PlexSensor(Entity):
    """Representation of a Plex now playing sensor."""

    def __init__(self, hass, plex_server):
        """Initialize the sensor."""
        self._state = None
        self._server = plex_server
        self._name = NAME_FORMAT.format(plex_server.friendly_name)
        self._unique_id = f"sensor-{plex_server.machine_identifier}"
        self.async_refresh_sensor = Debouncer(
            hass,
            _LOGGER,
            cooldown=3,
            immediate=False,
            function=self._async_refresh_sensor,
        ).async_call

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        server_id = self._server.machine_identifier
        unsub = async_dispatcher_connect(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(server_id),
            self.async_refresh_sensor,
        )
        self.hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    async def _async_refresh_sensor(self):
        """Set instance object and trigger an entity state update."""
        _LOGGER.debug("Refreshing sensor [%s]", self.unique_id)
        self._state = len(self._server.sensor_attributes)
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "Watching"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:plex"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._server.sensor_attributes

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.unique_id is None:
            return None

        return {
            "identifiers": {(PLEX_DOMAIN, self._server.machine_identifier)},
            "manufacturer": "Plex",
            "model": "Plex Media Server",
            "name": "Activity Sensor",
            "sw_version": self._server.version,
        }
