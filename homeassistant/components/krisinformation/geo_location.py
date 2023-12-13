"""Support for geolocation data from Krisinformation."""
from datetime import timedelta
from typing import Any

from krisinformation import crisis_alerter as krisinformation

# Importing necessary modules and classes.
from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START, UnitOfLength
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import DiscoveryInfoType

# Import custom costants and logger from the integration.
from .const import CONF_COUNTY

# Minimum time between updates for geolocation events.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

# Source identifier for Krisinformation geolocation events.
SOURCE = "krisinformation"


class KrisInformationGeolocationEvent(GeolocationEvent):
    """Custom GeolocationEvent class representing a demo Krisinformation geo-location event."""

    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_icon = "mdi:public"

    def __init__(
        self,
        external_id: str,
        name: str,
        latitude: float,
        longitude: float,
        unit_of_measurement: str,
        web: str,
        published: str,
        area: str,
    ) -> None:
        """Initialize entity with data provided."""
        self._external_id = external_id
        self._attr_name = name
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement
        self._web = web
        self._published = published  #: str | None = None
        self._area = area  #: str | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "link": self._web,
            "published": self._published,
            "county": self._area,
        }

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Responsible for setting up the Demo geolocations when a configuration entry is added to Home Assistant."""
    manager = KrisInformationGeolocationManager(
        hass,
        async_add_entities,
        krisinformation.CrisisAlerter(config.data.get(CONF_COUNTY)),
    )

    async def start_feed_manager(event: Event) -> None:
        """Start feed manager."""
        await manager.init_regular_updates()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_feed_manager)


class KrisInformationGeolocationManager:
    """Device manager for demo geolocation events."""

    def __init__(
        self,
        hass: HomeAssistant,
        async_add_entities: AddEntitiesCallback,
        crisis_alerter: krisinformation.CrisisAlerter,
    ) -> None:
        """Initialise the krisinformation geolocation event manager."""
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._events: list[KrisInformationGeolocationEvent] = []
        self._crisis_alerter = crisis_alerter

    def _generate_event(
        self,
        external_id: str,
        headline: str,
        latitude: float,
        longitude: float,
        web: str,
        published: str,
        area: str,
    ) -> KrisInformationGeolocationEvent:
        """Generate a krisinformation geolocation event."""
        return KrisInformationGeolocationEvent(
            external_id,
            headline,
            latitude,
            longitude,
            UnitOfLength.KILOMETERS,
            web,
            published,
            area,
        )

    async def init_regular_updates(self) -> None:
        """Initiate the scheduling of regular updates for geolocation events. Uses track_time_interval to schedule subsequent updates at fixed intervals."""
        await self._update()

        async_track_time_interval(
            self._hass,
            self._update,
            MIN_TIME_BETWEEN_UPDATES,
            cancel_on_shutdown=True,
        )

    async def _update(self, _=None) -> None:
        """Clear the existing list of geolocation events and fetches new geolocation events from the CrisisAlerter (Krisinformation API)."""
        new_events = []
        for existing_event in self._events:
            self._events.remove(existing_event)
            self._hass.add_job(existing_event.async_remove())

        def getvmas():
            return self._crisis_alerter.vmas(is_test=True)

        events = await self._hass.async_add_executor_job(getvmas)

        for event in events:
            new_event = KrisInformationGeolocationEvent(
                event["Identifier"],
                event["Headline"],
                event["Area"][0]["GeometryInformation"]["PoleOfInInaccessibility"][
                    "coordinates"
                ][1],
                event["Area"][0]["GeometryInformation"]["PoleOfInInaccessibility"][
                    "coordinates"
                ][0],
                UnitOfLength.KILOMETERS,
                event["Web"],
                event["Published"],
                event["Area"][0]["Description"],
            )
            new_events.append(new_event)
            self._events.append(new_event)
        self._async_add_entities(new_events)
