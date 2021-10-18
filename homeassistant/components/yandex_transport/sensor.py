"""Service for obtaining information about closer bus from Transport Yandex Service."""

from datetime import timedelta
import logging

from aioymaps import YandexMapsRequester
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

STOP_NAME = "stop_name"
USER_AGENT = "Home Assistant"
ATTRIBUTION = "Data provided by maps.yandex.ru"

CONF_STOP_ID = "stop_id"
CONF_ROUTE = "routes"

DEFAULT_NAME = "Yandex Transport"
ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUTE, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Yandex transport sensor."""
    stop_id = config[CONF_STOP_ID]
    name = config[CONF_NAME]
    routes = config[CONF_ROUTE]

    client_session = async_create_clientsession(hass, requote_redirect_url=False)
    data = YandexMapsRequester(user_agent=USER_AGENT, client_session=client_session)
    async_add_entities([DiscoverYandexTransport(data, stop_id, routes, name)], True)


class DiscoverYandexTransport(SensorEntity):
    """Implementation of yandex_transport sensor."""

    def __init__(self, requester: YandexMapsRequester, stop_id, routes, name):
        """Initialize sensor."""
        self.requester = requester
        self._stop_id = stop_id
        self._routes = []
        self._routes = routes
        self._state = None
        self._name = name
        self._attrs = None

    async def async_update(self, *, tries=0):
        """Get the latest data from maps.yandex.ru and update the states."""
        attrs = {}
        closer_time = None
        yandex_reply = await self.requester.get_stop_info(self._stop_id)
        try:
            data = yandex_reply["data"]
        except KeyError as key_error:
            _LOGGER.warning(
                "Exception KeyError was captured, missing key is %s. Yandex returned: %s",
                key_error,
                yandex_reply,
            )
            if tries > 0:
                return
            await self.requester.set_new_session()
            await self.async_update(tries=tries + 1)
            return

        stop_name = data["name"]
        transport_list = data["transports"]
        for transport in transport_list:
            route = transport["name"]
            for thread in transport["threads"]:
                if self._routes and route not in self._routes:
                    # skip unnecessary route info
                    continue
                if "Events" not in thread["BriefSchedule"]:
                    continue
                for event in thread["BriefSchedule"]["Events"]:
                    if "Estimated" not in event:
                        continue
                    posix_time_next = int(event["Estimated"]["value"])
                    if closer_time is None or closer_time > posix_time_next:
                        closer_time = posix_time_next
                    if route not in attrs:
                        attrs[route] = []
                    attrs[route].append(event["Estimated"]["text"])
        attrs[STOP_NAME] = stop_name
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        if closer_time is None:
            self._state = None
        else:
            self._state = dt_util.utc_from_timestamp(closer_time).isoformat(
                timespec="seconds"
            )
        self._attrs = attrs

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON
