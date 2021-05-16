"""Support for Plex media server monitoring."""
import logging

from plexapi.exceptions import NotFound

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_SERVER_IDENTIFIER,
    DOMAIN as PLEX_DOMAIN,
    NAME_FORMAT,
    PLEX_UPDATE_LIBRARY_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
    SERVERS,
)

LIBRARY_ATTRIBUTE_TYPES = {
    "artist": ["artist", "album"],
    "photo": ["photoalbum"],
    "show": ["show", "season"],
}

LIBRARY_PRIMARY_LIBTYPE = {
    "show": "episode",
    "artist": "track",
}

LIBRARY_ICON_LOOKUP = {
    "artist": "mdi:music",
    "movie": "mdi:movie",
    "photo": "mdi:image",
    "show": "mdi:television",
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plex sensor from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    plexserver = hass.data[PLEX_DOMAIN][SERVERS][server_id]
    sensors = [PlexSensor(hass, plexserver)]

    def create_library_sensors():
        """Create Plex library sensors with sync calls."""
        for library in plexserver.library.sections():
            sensors.append(PlexLibrarySectionSensor(hass, plexserver, library))

    await hass.async_add_executor_job(create_library_sensors)
    async_add_entities(sensors)


class PlexSensor(SensorEntity):
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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_SENSOR_SIGNAL.format(server_id),
                self.async_refresh_sensor,
            )
        )

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
    def extra_state_attributes(self):
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
            "name": self._server.friendly_name,
            "sw_version": self._server.version,
        }


class PlexLibrarySectionSensor(SensorEntity):
    """Representation of a Plex library section sensor."""

    def __init__(self, hass, plex_server, plex_library_section):
        """Initialize the sensor."""
        self._server = plex_server
        self.server_name = plex_server.friendly_name
        self.server_id = plex_server.machine_identifier
        self.library_section = plex_library_section
        self.library_type = plex_library_section.type
        self._name = f"{self.server_name} Library - {plex_library_section.title}"
        self._unique_id = f"library-{self.server_id}-{plex_library_section.uuid}"
        self._state = None
        self._available = True
        self._attributes = {}

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_LIBRARY_SIGNAL.format(self.server_id),
                self.async_refresh_sensor,
            )
        )
        await self.async_refresh_sensor()

    async def async_refresh_sensor(self):
        """Update state and attributes for the library sensor."""
        _LOGGER.debug("Refreshing library sensor for '%s'", self.name)
        try:
            await self.hass.async_add_executor_job(self._update_state_and_attrs)
            self._available = True
        except NotFound:
            self._available = False
        self.async_write_ha_state()

    def _update_state_and_attrs(self):
        """Update library sensor state with sync calls."""
        primary_libtype = LIBRARY_PRIMARY_LIBTYPE.get(
            self.library_type, self.library_type
        )

        self._state = self.library_section.totalViewSize(
            libtype=primary_libtype, includeCollections=False
        )
        for libtype in LIBRARY_ATTRIBUTE_TYPES.get(self.library_type, []):
            self._attributes[f"{libtype}s"] = self.library_section.totalViewSize(
                libtype=libtype, includeCollections=False
            )

    @property
    def available(self):
        """Return the availability of the client."""
        return self._available

    @property
    def entity_registry_enabled_default(self):
        """Return if sensor should be enabled by default."""
        return False

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
        return "Items"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return LIBRARY_ICON_LOOKUP.get(self.library_type, "mdi:plex")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.unique_id is None:
            return None

        return {
            "identifiers": {(PLEX_DOMAIN, self.server_id)},
            "manufacturer": "Plex",
            "model": "Plex Media Server",
            "name": self.server_name,
            "sw_version": self._server.version,
        }
