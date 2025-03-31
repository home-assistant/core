"""Get ride details and liveboard details for NMBS (Belgian railway)."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from pyrail import iRail
from pyrail.models import ConnectionDetails, LiveboardDeparture, StationDetails
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SHOW_ON_MAP,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (  # noqa: F401
    CONF_EXCLUDE_VIAS,
    CONF_STATION_FROM,
    CONF_STATION_LIVE,
    CONF_STATION_TO,
    DOMAIN,
    PLATFORMS,
    find_station,
    find_station_by_name,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NMBS"

DEFAULT_ICON = "mdi:train"
DEFAULT_ICON_ALERT = "mdi:alert-octagon"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_FROM): cv.string,
        vol.Required(CONF_STATION_TO): cv.string,
        vol.Optional(CONF_STATION_LIVE): cv.string,
        vol.Optional(CONF_EXCLUDE_VIAS, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
    }
)


def get_time_until(departure_time: datetime | None = None):
    """Calculate the time between now and a train's departure time."""
    if departure_time is None:
        return 0

    delta = dt_util.as_utc(departure_time) - dt_util.utcnow()
    return round(delta.total_seconds() / 60)


def get_delay_in_minutes(delay=0):
    """Get the delay in minutes from a delay in seconds."""
    return round(int(delay) / 60)


def get_ride_duration(departure_time: datetime, arrival_time: datetime, delay=0):
    """Calculate the total travel time in minutes."""
    duration = arrival_time - departure_time
    duration_time = int(round(duration.total_seconds() / 60))
    return duration_time + get_delay_in_minutes(delay)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NMBS sensor with iRail API."""

    if config[CONF_PLATFORM] == DOMAIN:
        if CONF_SHOW_ON_MAP not in config:
            config[CONF_SHOW_ON_MAP] = False
        if CONF_EXCLUDE_VIAS not in config:
            config[CONF_EXCLUDE_VIAS] = False

        station_types = [CONF_STATION_FROM, CONF_STATION_TO, CONF_STATION_LIVE]

        for station_type in station_types:
            station = (
                find_station_by_name(hass, config[station_type])
                if station_type in config
                else None
            )
            if station is None and station_type in config:
                async_create_issue(
                    hass,
                    DOMAIN,
                    "deprecated_yaml_import_issue_station_not_found",
                    breaks_in_ha_version="2025.7.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml_import_issue_station_not_found",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": "NMBS",
                        "station_name": config[station_type],
                        "url": "/config/integrations/dashboard/add?domain=nmbs",
                    },
                )
                return

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config,
            )
        )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "NMBS",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NMBS sensor entities based on a config entry."""
    api_client = iRail(session=async_get_clientsession(hass))

    name = config_entry.data.get(CONF_NAME, None)
    show_on_map = config_entry.data.get(CONF_SHOW_ON_MAP, False)
    excl_vias = config_entry.data.get(CONF_EXCLUDE_VIAS, False)

    station_from = find_station(hass, config_entry.data[CONF_STATION_FROM])
    station_to = find_station(hass, config_entry.data[CONF_STATION_TO])

    # setup the connection from station to station
    # setup a disabled liveboard for both from and to station
    async_add_entities(
        [
            NMBSSensor(
                api_client, name, show_on_map, station_from, station_to, excl_vias
            ),
            NMBSLiveBoard(
                api_client, station_from, station_from, station_to, excl_vias
            ),
            NMBSLiveBoard(api_client, station_to, station_from, station_to, excl_vias),
        ]
    )


class NMBSLiveBoard(SensorEntity):
    """Get the next train from a station's liveboard."""

    _attr_attribution = "https://api.irail.be/"

    def __init__(
        self,
        api_client: iRail,
        live_station: StationDetails,
        station_from: StationDetails,
        station_to: StationDetails,
        excl_vias: bool,
    ) -> None:
        """Initialize the sensor for getting liveboard data."""
        self._station = live_station
        self._api_client = api_client
        self._station_from = station_from
        self._station_to = station_to

        self._excl_vias = excl_vias
        self._attrs: LiveboardDeparture | None = None

        self._state: str | None = None

        self.entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the sensor default name."""
        return f"Trains in {self._station.standard_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""

        unique_id = f"{self._station.id}_{self._station_from.id}_{self._station_to.id}"
        vias = "_excl_vias" if self._excl_vias else ""
        return f"nmbs_live_{unique_id}{vias}"

    @property
    def icon(self) -> str:
        """Return the default icon or an alert icon if delays."""
        if self._attrs and int(self._attrs.delay) > 0:
            return DEFAULT_ICON_ALERT

        return DEFAULT_ICON

    @property
    def native_value(self) -> str | None:
        """Return sensor state."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the sensor attributes if data is available."""
        if self._state is None or not self._attrs:
            return None

        delay = get_delay_in_minutes(self._attrs.delay)
        departure = get_time_until(self._attrs.time)

        attrs = {
            "departure": f"In {departure} minutes",
            "departure_minutes": departure,
            "extra_train": self._attrs.is_extra,
            "vehicle_id": self._attrs.vehicle,
            "monitored_station": self._station.standard_name,
        }

        if delay > 0:
            attrs["delay"] = f"{delay} minutes"
            attrs["delay_minutes"] = delay

        return attrs

    async def async_update(self, **kwargs: Any) -> None:
        """Set the state equal to the next departure."""
        liveboard = await self._api_client.get_liveboard(self._station.id)

        if liveboard is None:
            _LOGGER.warning("API failed in NMBSLiveBoard")
            return

        if not (departures := liveboard.departures):
            _LOGGER.warning("API returned invalid departures: %r", liveboard)
            return

        _LOGGER.debug("API returned departures: %r", departures)
        if len(departures) == 0:
            # No trains are scheduled
            return
        next_departure = departures[0]

        self._attrs = next_departure
        self._state = f"Track {next_departure.platform} - {next_departure.station}"


class NMBSSensor(SensorEntity):
    """Get the total travel time for a given connection."""

    _attr_attribution = "https://api.irail.be/"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        api_client: iRail,
        name: str,
        show_on_map: bool,
        station_from: StationDetails,
        station_to: StationDetails,
        excl_vias: bool,
    ) -> None:
        """Initialize the NMBS connection sensor."""
        self._name = name
        self._show_on_map = show_on_map
        self._api_client = api_client
        self._station_from = station_from
        self._station_to = station_to
        self._excl_vias = excl_vias

        self._attrs: ConnectionDetails | None = None
        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        unique_id = f"{self._station_from.id}_{self._station_to.id}"

        vias = "_excl_vias" if self._excl_vias else ""
        return f"nmbs_connection_{unique_id}{vias}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if self._name is None:
            return f"Train from {self._station_from.standard_name} to {self._station_to.standard_name}"
        return self._name

    @property
    def icon(self) -> str:
        """Return the sensor default icon or an alert icon if any delay."""
        if self._attrs:
            delay = get_delay_in_minutes(self._attrs.departure.delay)
            if delay > 0:
                return "mdi:alert-octagon"

        return "mdi:train"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return sensor attributes if data is available."""
        if self._state is None or not self._attrs:
            return None

        delay = get_delay_in_minutes(self._attrs.departure.delay)
        departure = get_time_until(self._attrs.departure.time)
        canceled = self._attrs.departure.canceled

        attrs = {
            "destination": self._attrs.departure.station,
            "direction": self._attrs.departure.direction.name,
            "platform_arriving": self._attrs.arrival.platform,
            "platform_departing": self._attrs.departure.platform,
            "vehicle_id": self._attrs.departure.vehicle,
        }

        if not canceled:
            attrs["departure"] = f"In {departure} minutes"
            attrs["departure_minutes"] = departure
            attrs["canceled"] = False
        else:
            attrs["departure"] = None
            attrs["departure_minutes"] = None
            attrs["canceled"] = True

        if self._show_on_map and self.station_coordinates:
            attrs[ATTR_LATITUDE] = self.station_coordinates[0]
            attrs[ATTR_LONGITUDE] = self.station_coordinates[1]

        if self.is_via_connection and not self._excl_vias:
            via = self._attrs.vias[0]

            attrs["via"] = via.station
            attrs["via_arrival_platform"] = via.arrival.platform
            attrs["via_transfer_platform"] = via.departure.platform
            attrs["via_transfer_time"] = get_delay_in_minutes(
                via.timebetween
            ) + get_delay_in_minutes(via.departure.delay)

        if delay > 0:
            attrs["delay"] = f"{delay} minutes"
            attrs["delay_minutes"] = delay

        return attrs

    @property
    def native_value(self) -> int | None:
        """Return the state of the device."""
        return self._state

    @property
    def station_coordinates(self) -> list[float]:
        """Get the lat, long coordinates for station."""
        if self._state is None or not self._attrs:
            return []

        latitude = float(self._attrs.departure.station_info.latitude)
        longitude = float(self._attrs.departure.station_info.longitude)
        return [latitude, longitude]

    @property
    def is_via_connection(self) -> bool:
        """Return whether the connection goes through another station."""
        if not self._attrs:
            return False

        return self._attrs.vias is not None and len(self._attrs.vias) > 0

    async def async_update(self, **kwargs: Any) -> None:
        """Set the state to the duration of a connection."""
        connections = await self._api_client.get_connections(
            self._station_from.id, self._station_to.id
        )

        if connections is None:
            _LOGGER.warning("API failed in NMBSSensor")
            return

        if not (connection := connections.connections):
            _LOGGER.warning("API returned invalid connection: %r", connections)
            return

        _LOGGER.debug("API returned connection: %r", connection)
        if connection[0].departure.left:
            next_connection = connection[1]
        else:
            next_connection = connection[0]

        self._attrs = next_connection

        if self._excl_vias and self.is_via_connection:
            _LOGGER.debug(
                "Skipping update of NMBSSensor because this connection is a via"
            )
            return

        duration = get_ride_duration(
            next_connection.departure.time,
            next_connection.arrival.time,
            next_connection.departure.delay,
        )

        self._state = duration
