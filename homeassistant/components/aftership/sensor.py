"""Support for non-delivered packages recorded in AfterShip."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ["pyaftership==0.1.2"]

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Information provided by AfterShip"
ATTR_TRACKINGS = "trackings"

BASE_LINK = "https://track.aftership.com/"

CONF_SLUG = "slug"
CONF_TITLE = "title"
CONF_TRACKING_NUMBER = "tracking_number"

DEFAULT_NAME = "aftership"

ICON = "mdi:package-variant-closed"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

SERVICE_ADD_TRACKING = "aftership_add_tracking"
SERVICE_REMOVE_TRACKING = "aftership_remove_tracking"

ADD_TRACKING_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TRACKING_NUMBER): cv.string,
        vol.Optional(CONF_TITLE): cv.string,
        vol.Optional(CONF_SLUG): cv.string,
    }
)

REMOVE_TRACKING_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(CONF_SLUG): cv.string,
     vol.Required(CONF_TRACKING_NUMBER): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the AfterShip sensor platform."""
    from pyaftership.tracker import Tracking

    apikey = config[CONF_API_KEY]
    name = config[CONF_NAME]
    session = async_get_clientsession(hass)
    aftership = Tracking(hass.loop, session, apikey)

    await aftership.get_trackings()

    if not aftership.meta or aftership.meta["code"] != 200:
        _LOGGER.error(
            "No tracking data found. Check API key is correct: %s",
            aftership.meta
        )
        return

    async_add_entities([AfterShipSensor(aftership, name)], True)

    async def handle_add_tracking(call):
        """Call when a user adds a new Aftership tracking from HASS."""
        title = call.data.get(CONF_TITLE)
        slug = call.data.get(CONF_SLUG)
        tracking_number = call.data[CONF_TRACKING_NUMBER]

        await aftership.add_package_tracking(tracking_number, title, slug)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TRACKING,
        handle_add_tracking,
        schema=ADD_TRACKING_SERVICE_SCHEMA,
    )

    async def handle_remove_tracking(call):
        """Call when a user removes an Aftership tracking from HASS."""
        slug = call.data[CONF_SLUG]
        tracking_number = call.data[CONF_TRACKING_NUMBER]

        await aftership.remove_package_tracking(slug, tracking_number)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TRACKING,
        handle_remove_tracking,
        schema=REMOVE_TRACKING_SERVICE_SCHEMA,
    )


class AfterShipSensor(Entity):
    """Representation of a AfterShip sensor."""

    def __init__(self, aftership, name):
        """Initialize the sensor."""
        self._attributes = {}
        self._name = name
        self._state = None
        self.aftership = aftership

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "packages"

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the AfterShip API."""
        await self.aftership.get_trackings()

        if not self.aftership.meta:
            _LOGGER.error("Unknown errors when querying")
            return
        if self.aftership.meta["code"] != 200:
            _LOGGER.error(
                "Errors when querying AfterShip. %s",
                str(self.aftership.meta)
            )
            return

        status_to_ignore = {"delivered"}
        status_counts = {}
        trackings = []
        not_delivered_count = 0

        for tracking in self.aftership.trackings["trackings"]:
            status = tracking["tag"].lower()
            name = (
                tracking["tracking_number"]
                if tracking["title"] is None
                else tracking["title"]
            )
            status_counts[status] = status_counts.get(status, 0) + 1
            trackings.append({
                "name": name,
                "tracking_number": tracking["tracking_number"],
                "slug": tracking["slug"],
                "link": BASE_LINK
                + tracking["slug"]
                + "/"
                + tracking["tracking_number"],
                "last_update": tracking["updated_at"],
                "status": tracking["tag"],
            })

            if status not in status_to_ignore:
                not_delivered_count += 1
            else:
                _LOGGER.debug("Ignoring %s as it has status: %s",
                              name, status)

        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            **status_counts,
            ATTR_TRACKINGS: trackings,
        }

        self._state = not_delivered_count
