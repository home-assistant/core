"""Support for Plex media server monitoring."""
from __future__ import annotations

import logging

from plexapi.exceptions import NotFound
import requests.exceptions

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_UPDATE_LIBRARY_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
)
from .helpers import get_plex_server, pretty_title

LIBRARY_ATTRIBUTE_TYPES = {
    "artist": ["artist", "album"],
    "photo": ["photoalbum"],
    "show": ["show", "season"],
}

LIBRARY_PRIMARY_LIBTYPE = {
    "show": "episode",
    "artist": "track",
}

LIBRARY_RECENT_LIBTYPE = {
    "show": "episode",
    "artist": "album",
}

LIBRARY_ICON_LOOKUP = {
    "artist": "mdi:music",
    "movie": "mdi:movie",
    "photo": "mdi:image",
    "show": "mdi:television",
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex sensor from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    plexserver = get_plex_server(hass, server_id)
    sensors = [PlexSensor(hass, plexserver)]

    def create_library_sensors():
        """Create Plex library sensors with sync calls."""
        for library in plexserver.library.sections():
            sensors.append(PlexLibrarySectionSensor(hass, plexserver, library))

    await hass.async_add_executor_job(create_library_sensors)
    async_add_entities(sensors)


class PlexSensor(SensorEntity):
    """Representation of a Plex now playing sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:plex"
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "watching"

    def __init__(self, hass, plex_server):
        """Initialize the sensor."""
        self._attr_unique_id = f"sensor-{plex_server.machine_identifier}"

        self._server = plex_server
        self.async_refresh_sensor = Debouncer(
            hass,
            _LOGGER,
            cooldown=3,
            immediate=False,
            function=self._async_refresh_sensor,
        ).async_call

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        server_id = self._server.machine_identifier
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_SENSOR_SIGNAL.format(server_id),
                self.async_refresh_sensor,
            )
        )

    async def _async_refresh_sensor(self) -> None:
        """Set instance object and trigger an entity state update."""
        _LOGGER.debug("Refreshing sensor [%s]", self.unique_id)
        self._attr_native_value = len(self._server.sensor_attributes)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._server.sensor_attributes

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._server.machine_identifier)},
            manufacturer="Plex",
            model="Plex Media Server",
            name=self._server.friendly_name,
            sw_version=self._server.version,
            configuration_url=f"{self._server.url_in_use}/web",
        )


class PlexLibrarySectionSensor(SensorEntity):
    """Representation of a Plex library section sensor."""

    _attr_available = True
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "Items"

    def __init__(self, hass, plex_server, plex_library_section):
        """Initialize the sensor."""
        self._server = plex_server
        self.server_name = plex_server.friendly_name
        self.server_id = plex_server.machine_identifier
        self.library_section = plex_library_section
        self.library_type = plex_library_section.type

        self._attr_extra_state_attributes = {}
        self._attr_icon = LIBRARY_ICON_LOOKUP.get(self.library_type, "mdi:plex")
        self._attr_name = f"{self.server_name} Library - {plex_library_section.title}"
        self._attr_unique_id = f"library-{self.server_id}-{plex_library_section.uuid}"

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_LIBRARY_SIGNAL.format(self.server_id),
                self.async_refresh_sensor,
            )
        )
        await self.async_refresh_sensor()

    async def async_refresh_sensor(self) -> None:
        """Update state and attributes for the library sensor."""
        _LOGGER.debug("Refreshing library sensor for '%s'", self.name)
        try:
            await self.hass.async_add_executor_job(self._update_state_and_attrs)
            self._attr_available = True
        except NotFound:
            self._attr_available = False
        except requests.exceptions.RequestException as err:
            _LOGGER.error(
                "Could not update library sensor for '%s': %s",
                self.library_section.title,
                err,
            )
            self._attr_available = False
        self.async_write_ha_state()

    def _update_state_and_attrs(self):
        """Update library sensor state with sync calls."""
        primary_libtype = LIBRARY_PRIMARY_LIBTYPE.get(
            self.library_type, self.library_type
        )

        self._attr_native_value = self.library_section.totalViewSize(
            libtype=primary_libtype, includeCollections=False
        )
        for libtype in LIBRARY_ATTRIBUTE_TYPES.get(self.library_type, []):
            self._attr_extra_state_attributes[
                f"{libtype}s"
            ] = self.library_section.totalViewSize(
                libtype=libtype, includeCollections=False
            )

        recent_libtype = LIBRARY_RECENT_LIBTYPE.get(
            self.library_type, self.library_type
        )
        recently_added = self.library_section.recentlyAdded(
            maxresults=1, libtype=recent_libtype
        )
        if recently_added:
            media = recently_added[0]
            self._attr_extra_state_attributes["last_added_item"] = pretty_title(media)
            self._attr_extra_state_attributes["last_added_timestamp"] = media.addedAt

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        if self.unique_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self.server_id)},
            manufacturer="Plex",
            model="Plex Media Server",
            name=self.server_name,
            sw_version=self._server.version,
            configuration_url=f"{self._server.url_in_use}/web",
        )
