"""Support for geolocation data from Krisinformation."""
from datetime import timedelta
from typing import Any

from krisinformation import crisis_alerter as krisinformation

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START, UnitOfLength
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_COUNTY

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

SOURCE = "krisinformation"


class KrisInformationGeolocationEvent(GeolocationEvent):
    """Represents a krisinformation geolocation event."""

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
        state: str,
    ) -> None:
        """Initialize entity with data provided."""
        self._external_id = external_id
        self._attr_name = name
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement
        self._web = web
        self._published = published
        self._area = area
        self._state = state

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

    @property
    def state(self):
        """Return the state of the geolocation event."""
        return self._state


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the krisinformation geolocations."""
    manager = KrisInformationGeolocationManager(
        hass,
        async_add_entities,
        krisinformation.CrisisAlerter(config.data.get(CONF_COUNTY)),
    )

    # await hass.async_add_executor_job()
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


    async def init_regular_updates(self) -> None:
        """Schedule regular updates based on configured time interval."""
        await self._update()

        async_track_time_interval(
            self._hass,
            self._update,
            MIN_TIME_BETWEEN_UPDATES,
            cancel_on_shutdown=True,
        )

    async def _update(self, _=None) -> None:
        """Remove events and add new random events."""
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
                ""
            )
            new_events.append(new_event)
            self._events.append(new_event)
        self._async_add_entities(new_events)
