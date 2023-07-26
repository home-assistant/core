"""Sensor for the Open Sky Network."""
from __future__ import annotations

from datetime import timedelta

from python_opensky import BoundingBox, OpenSky, StateVector
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ALTITUDE,
    ATTR_CALLSIGN,
    ATTR_ICAO24,
    ATTR_SENSOR,
    CLIENT,
    CONF_ALTITUDE,
    DEFAULT_ALTITUDE,
    DOMAIN,
    EVENT_OPENSKY_ENTRY,
    EVENT_OPENSKY_EXIT,
)

# OpenSky free user has 400 credits, with 4 credits per API call. 100/24 = ~4 requests per hour
SCAN_INTERVAL = timedelta(minutes=15)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RADIUS): vol.Coerce(float),
        vol.Optional(CONF_NAME): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_ALTITUDE, default=DEFAULT_ALTITUDE): vol.Coerce(float),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OpenSky sensor platform from yaml."""

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.1.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "OpenSky",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    opensky = hass.data[DOMAIN][entry.entry_id][CLIENT]
    bounding_box = OpenSky.get_bounding_box(
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        entry.options[CONF_RADIUS],
    )
    async_add_entities(
        [
            OpenSkySensor(
                entry.title,
                opensky,
                bounding_box,
                entry.options.get(CONF_ALTITUDE, DEFAULT_ALTITUDE),
                entry.entry_id,
            )
        ],
        True,
    )


class OpenSkySensor(SensorEntity):
    """Open Sky Network Sensor."""

    _attr_attribution = (
        "Information provided by the OpenSky Network (https://opensky-network.org)"
    )

    def __init__(
        self,
        name: str,
        opensky: OpenSky,
        bounding_box: BoundingBox,
        altitude: float,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._altitude = altitude
        self._state = 0
        self._name = name
        self._previously_tracked: set[str] = set()
        self._opensky = opensky
        self._bounding_box = bounding_box
        self._attr_unique_id = f"{entry_id}_opensky"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state

    def _handle_boundary(
        self, flights: set[str], event: str, metadata: dict[str, StateVector]
    ) -> None:
        """Handle flights crossing region boundary."""
        for flight in flights:
            if flight in metadata:
                altitude = metadata[flight].barometric_altitude
                longitude = metadata[flight].longitude
                latitude = metadata[flight].latitude
                icao24 = metadata[flight].icao24
            else:
                # Assume Flight has landed if missing.
                altitude = 0
                longitude = None
                latitude = None
                icao24 = None

            data = {
                ATTR_CALLSIGN: flight,
                ATTR_ALTITUDE: altitude,
                ATTR_SENSOR: self._name,
                ATTR_LONGITUDE: longitude,
                ATTR_LATITUDE: latitude,
                ATTR_ICAO24: icao24,
            }
            self.hass.bus.fire(event, data)

    async def async_update(self) -> None:
        """Update device state."""
        currently_tracked = set()
        flight_metadata: dict[str, StateVector] = {}
        response = await self._opensky.get_states(bounding_box=self._bounding_box)
        for flight in response.states:
            if not flight.callsign:
                continue
            callsign = flight.callsign.strip()
            if callsign != "":
                flight_metadata[callsign] = flight
            else:
                continue
            if (
                flight.longitude is None
                or flight.latitude is None
                or flight.on_ground
                or flight.barometric_altitude is None
            ):
                continue
            altitude = flight.barometric_altitude
            if altitude > self._altitude and self._altitude != 0:
                continue
            currently_tracked.add(callsign)
        if self._previously_tracked is not None:
            entries = currently_tracked - self._previously_tracked
            exits = self._previously_tracked - currently_tracked
            self._handle_boundary(entries, EVENT_OPENSKY_ENTRY, flight_metadata)
            self._handle_boundary(exits, EVENT_OPENSKY_EXIT, flight_metadata)
        self._state = len(currently_tracked)
        self._previously_tracked = currently_tracked

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "flights"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:airplane"
