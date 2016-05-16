"""
Support for Google travel time sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.google_travel_time/
"""
from datetime import datetime
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_API_KEY, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['googlemaps==2.4.3']

# Return cached results if last update was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONF_ORIGIN = 'origin'
CONF_DESTINATION = 'destination'
CONF_TRAVEL_MODE = 'travel_mode'
CONF_OPTIONS = 'options'
CONF_MODE = 'mode'
CONF_NAME = 'name'

ALL_LANGUAGES = ['ar', 'bg', 'bn', 'ca', 'cs', 'da', 'de', 'el', 'en', 'es',
                 'eu', 'fa', 'fi', 'fr', 'gl', 'gu', 'hi', 'hr', 'hu', 'id',
                 'it', 'iw', 'ja', 'kn', 'ko', 'lt', 'lv', 'ml', 'mr', 'nl',
                 'no', 'pl', 'pt', 'pt-BR', 'pt-PT', 'ro', 'ru', 'sk', 'sl',
                 'sr', 'sv', 'ta', 'te', 'th', 'tl', 'tr', 'uk', 'vi',
                 'zh-CN', 'zh-TW']

TRANSIT_PREFS = ['less_walking', 'fewer_transfers']

PLATFORM_SCHEMA = vol.Schema({
    vol.Required('platform'): 'google_travel_time',
    vol.Optional(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_API_KEY): vol.Coerce(str),
    vol.Required(CONF_ORIGIN): vol.Coerce(str),
    vol.Required(CONF_DESTINATION): vol.Coerce(str),
    vol.Optional(CONF_TRAVEL_MODE):
        vol.In(["driving", "walking", "bicycling", "transit"]),
    vol.Optional(CONF_OPTIONS, default=dict()): vol.All(
        dict, vol.Schema({
            vol.Optional(CONF_MODE, default='driving'):
                vol.In(["driving", "walking", "bicycling", "transit"]),
            vol.Optional('language'): vol.In(ALL_LANGUAGES),
            vol.Optional('avoid'): vol.In(['tolls', 'highways',
                                           'ferries', 'indoor']),
            vol.Optional('units'): vol.In(['metric', 'imperial']),
            vol.Exclusive('arrival_time', 'time'): cv.string,
            vol.Exclusive('departure_time', 'time'): cv.string,
            vol.Optional('traffic_model'): vol.In(['best_guess',
                                                   'pessimistic',
                                                   'optimistic']),
            vol.Optional('transit_mode'): vol.In(['bus', 'subway', 'train',
                                                  'tram', 'rail']),
            vol.Optional('transit_routing_preference'): vol.In(TRANSIT_PREFS)
        }))
})


def convert_time_to_utc(timestr):
    """Take a string like 08:00:00 and convert it to a unix timestamp."""
    combined = datetime.combine(dt_util.start_of_local_day(),
                                dt_util.parse_time(timestr))
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return dt_util.as_timestamp(combined)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the travel time platform."""
    # pylint: disable=too-many-locals
    options = config.get(CONF_OPTIONS)

    if options.get('units') is None:
        if hass.config.temperature_unit is TEMP_CELSIUS:
            options['units'] = 'metric'
        elif hass.config.temperature_unit is TEMP_FAHRENHEIT:
            options['units'] = 'imperial'

    travel_mode = config.get(CONF_TRAVEL_MODE)
    mode = options.get(CONF_MODE)

    if travel_mode is not None:
        wstr = ("Google Travel Time: travel_mode is deprecated, please add "
                "mode to the options dictionary instead!")
        _LOGGER.warning(wstr)
        if mode is None:
            options[CONF_MODE] = travel_mode

    titled_mode = options.get(CONF_MODE).title()
    formatted_name = "Google Travel Time - {}".format(titled_mode)
    name = config.get(CONF_NAME, formatted_name)
    api_key = config.get(CONF_API_KEY)
    origin = config.get(CONF_ORIGIN)
    destination = config.get(CONF_DESTINATION)

    sensor = GoogleTravelTimeSensor(name, api_key, origin, destination,
                                    options)

    if sensor.valid_api_connection:
        add_devices_callback([sensor])


# pylint: disable=too-many-instance-attributes
class GoogleTravelTimeSensor(Entity):
    """Representation of a tavel time sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, api_key, origin, destination, options):
        """Initialize the sensor."""
        self._name = name
        self._options = options
        self._origin = origin
        self._destination = destination
        self._matrix = None
        self.valid_api_connection = True

        import googlemaps
        self._client = googlemaps.Client(api_key, timeout=10)
        try:
            self.update()
        except googlemaps.exceptions.ApiError as exp:
            _LOGGER .error(exp)
            self.valid_api_connection = False
            return

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            res = self._matrix['rows'][0]['elements'][0]['duration']['value']
            return round(res/60)
        except KeyError:
            return None

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        res = self._matrix.copy()
        res.update(self._options)
        del res['rows']
        _data = self._matrix['rows'][0]['elements'][0]
        if 'duration_in_traffic' in _data:
            res['duration_in_traffic'] = _data['duration_in_traffic']['text']
        if 'duration' in _data:
            res['duration'] = _data['duration']['text']
        if 'distance' in _data:
            res['distance'] = _data['distance']['text']
        return res

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Google."""
        options_copy = self._options.copy()
        dtime = options_copy.get('departure_time')
        atime = options_copy.get('arrival_time')
        if dtime is not None and ':' in dtime:
            options_copy['departure_time'] = convert_time_to_utc(dtime)

        if atime is not None and ':' in atime:
            options_copy['arrival_time'] = convert_time_to_utc(atime)

        self._matrix = self._client.distance_matrix(self._origin,
                                                    self._destination,
                                                    **options_copy)
