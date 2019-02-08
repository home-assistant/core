"""
Support for Ambient Weather Station Service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ambient_station/
"""
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_NAME, ATTR_LOCATION, CONF_API_KEY, CONF_MONITORED_CONDITIONS,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .config_flow import configured_instances
from .const import (
    ATTR_LAST_DATA, CONF_APP_KEY, DATA_CLIENT, DOMAIN, TOPIC_UPDATE,
    TYPE_BINARY_SENSOR, TYPE_SENSOR)

REQUIREMENTS = ['aioambient==0.1.0']
_LOGGER = logging.getLogger(__name__)

DEFAULT_SOCKET_MIN_RETRY = 15

TYPE_24HOURRAININ = '24hourrainin'
TYPE_BAROMABSIN = 'baromabsin'
TYPE_BAROMRELIN = 'baromrelin'
TYPE_BATTOUT = 'battout'
TYPE_CO2 = 'co2'
TYPE_DAILYRAININ = 'dailyrainin'
TYPE_DEWPOINT = 'dewPoint'
TYPE_EVENTRAININ = 'eventrainin'
TYPE_FEELSLIKE = 'feelsLike'
TYPE_HOURLYRAININ = 'hourlyrainin'
TYPE_HUMIDITY = 'humidity'
TYPE_HUMIDITYIN = 'humidityin'
TYPE_LASTRAIN = 'lastRain'
TYPE_MAXDAILYGUST = 'maxdailygust'
TYPE_MONTHLYRAININ = 'monthlyrainin'
TYPE_SOLARRADIATION = 'solarradiation'
TYPE_TEMPF = 'tempf'
TYPE_TEMPINF = 'tempinf'
TYPE_TOTALRAININ = 'totalrainin'
TYPE_UV = 'uv'
TYPE_WEEKLYRAININ = 'weeklyrainin'
TYPE_WINDDIR = 'winddir'
TYPE_WINDDIR_AVG10M = 'winddir_avg10m'
TYPE_WINDDIR_AVG2M = 'winddir_avg2m'
TYPE_WINDGUSTDIR = 'windgustdir'
TYPE_WINDGUSTMPH = 'windgustmph'
TYPE_WINDSPDMPH_AVG10M = 'windspdmph_avg10m'
TYPE_WINDSPDMPH_AVG2M = 'windspdmph_avg2m'
TYPE_WINDSPEEDMPH = 'windspeedmph'
TYPE_YEARLYRAININ = 'yearlyrainin'
SENSOR_TYPES = {
    TYPE_24HOURRAININ: ('24 Hr Rain', 'in', TYPE_SENSOR, None),
    TYPE_BAROMABSIN: ('Abs Pressure', 'inHg', TYPE_SENSOR, None),
    TYPE_BAROMRELIN: ('Rel Pressure', 'inHg', TYPE_SENSOR, None),
    TYPE_BATTOUT: ('Battery', None, TYPE_BINARY_SENSOR, 'battery'),
    TYPE_CO2: ('co2', 'ppm', TYPE_SENSOR, None),
    TYPE_DAILYRAININ: ('Daily Rain', 'in', TYPE_SENSOR, None),
    TYPE_DEWPOINT: ('Dew Point', '°F', TYPE_SENSOR, None),
    TYPE_EVENTRAININ: ('Event Rain', 'in', TYPE_SENSOR, None),
    TYPE_FEELSLIKE: ('Feels Like', '°F', TYPE_SENSOR, None),
    TYPE_HOURLYRAININ: ('Hourly Rain Rate', 'in/hr', TYPE_SENSOR, None),
    TYPE_HUMIDITY: ('Humidity', '%', TYPE_SENSOR, None),
    TYPE_HUMIDITYIN: ('Humidity In', '%', TYPE_SENSOR, None),
    TYPE_LASTRAIN: ('Last Rain', None, TYPE_SENSOR, None),
    TYPE_MAXDAILYGUST: ('Max Gust', 'mph', TYPE_SENSOR, None),
    TYPE_MONTHLYRAININ: ('Monthly Rain', 'in', TYPE_SENSOR, None),
    TYPE_SOLARRADIATION: ('Solar Rad', 'W/m^2', TYPE_SENSOR, None),
    TYPE_TEMPF: ('Temp', '°F', TYPE_SENSOR, None),
    TYPE_TEMPINF: ('Inside Temp', '°F', TYPE_SENSOR, None),
    TYPE_TOTALRAININ: ('Lifetime Rain', 'in', TYPE_SENSOR, None),
    TYPE_UV: ('uv', 'Index', TYPE_SENSOR, None),
    TYPE_WEEKLYRAININ: ('Weekly Rain', 'in', TYPE_SENSOR, None),
    TYPE_WINDDIR: ('Wind Dir', '°', TYPE_SENSOR, None),
    TYPE_WINDDIR_AVG10M: ('Wind Dir Avg 10m', '°', TYPE_SENSOR, None),
    TYPE_WINDDIR_AVG2M: ('Wind Dir Avg 2m', 'mph', TYPE_SENSOR, None),
    TYPE_WINDGUSTDIR: ('Gust Dir', '°', TYPE_SENSOR, None),
    TYPE_WINDGUSTMPH: ('Wind Gust', 'mph', TYPE_SENSOR, None),
    TYPE_WINDSPDMPH_AVG10M: ('Wind Avg 10m', 'mph', TYPE_SENSOR, None),
    TYPE_WINDSPDMPH_AVG2M: ('Wind Avg 2m', 'mph', TYPE_SENSOR, None),
    TYPE_WINDSPEEDMPH: ('Wind Speed', 'mph', TYPE_SENSOR, None),
    TYPE_YEARLYRAININ: ('Yearly Rain', 'in', TYPE_SENSOR, None),
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN:
        vol.Schema({
            vol.Required(CONF_APP_KEY): cv.string,
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_MONITORED_CONDITIONS):
                vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
        })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Ambient PWS component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_APP_KEY] in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={'source': SOURCE_IMPORT}, data=conf))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Ambient PWS as config entry."""
    from aioambient import Client
    from aioambient.errors import WebsocketConnectionError

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        ambient = AmbientStation(
            hass, config_entry,
            Client(
                config_entry.data[CONF_API_KEY],
                config_entry.data[CONF_APP_KEY], session),
            config_entry.data.get(CONF_MONITORED_CONDITIONS, []))
        hass.loop.create_task(ambient.ws_connect())
        hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = ambient
    except WebsocketConnectionError as err:
        _LOGGER.error('Config entry failed: %s', err)
        raise ConfigEntryNotReady

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, ambient.client.websocket.disconnect())

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an Ambient PWS config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    hass.async_create_task(ambient.ws_disconnect())

    for component in ('binary_sensor', 'sensor'):
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    return True


class AmbientStation:
    """Define a class to handle the Ambient websocket."""

    def __init__(self, hass, config_entry, client, monitored_conditions):
        """Initialize."""
        self._config_entry = config_entry
        self._hass = hass
        self._ws_reconnect_delay = DEFAULT_SOCKET_MIN_RETRY
        self.client = client
        self.monitored_conditions = monitored_conditions
        self.stations = {}

    async def ws_connect(self):
        """Register handlers and connect to the websocket."""
        from aioambient.errors import WebsocketError

        def on_connect():
            """Define a handler to fire when the websocket is connected."""
            _LOGGER.info('Connected to websocket')

        def on_data(data):
            """Define a handler to fire when the data is received."""
            mac_address = data['macAddress']
            if data != self.stations[mac_address][ATTR_LAST_DATA]:
                _LOGGER.debug('New data received: %s', data)
                self.stations[mac_address][ATTR_LAST_DATA] = data
                async_dispatcher_send(self._hass, TOPIC_UPDATE)

        def on_disconnect():
            """Define a handler to fire when the websocket is disconnected."""
            _LOGGER.info('Disconnected from websocket')

        def on_subscribed(data):
            """Define a handler to fire when the subscription is set."""
            for station in data['devices']:
                if station['macAddress'] in self.stations:
                    continue

                _LOGGER.debug('New station subscription: %s', data)

                # If the user hasn't specified monitored conditions, use only
                # those that their station supports (and which are defined
                # here):
                if not self.monitored_conditions:
                    self.monitored_conditions = [
                        k for k in station['lastData'].keys()
                        if k in SENSOR_TYPES
                    ]

                self.stations[station['macAddress']] = {
                    ATTR_LAST_DATA: station['lastData'],
                    ATTR_LOCATION: station['info']['location'],
                    ATTR_NAME: station['info']['name'],
                }

            for component in ('binary_sensor', 'sensor'):
                self._hass.async_create_task(
                    self._hass.config_entries.async_forward_entry_setup(
                        self._config_entry, component))

                self._ws_reconnect_delay = DEFAULT_SOCKET_MIN_RETRY

        self.client.websocket.on_connect(on_connect)
        self.client.websocket.on_data(on_data)
        self.client.websocket.on_disconnect(on_disconnect)
        self.client.websocket.on_subscribed(on_subscribed)

        try:
            await self.client.websocket.connect()
        except WebsocketError as err:
            _LOGGER.error("Error with the websocket connection: %s", err)

            self._ws_reconnect_delay = min(2 * self._ws_reconnect_delay, 480)

            async_call_later(
                self._hass, self._ws_reconnect_delay, self.ws_connect)

    async def ws_disconnect(self):
        """Disconnect from the websocket."""
        await self.client.websocket.disconnect()


class AmbientWeatherEntity(Entity):
    """Define a base Ambient PWS entity."""

    def __init__(
            self, ambient, mac_address, station_name, sensor_type,
            sensor_name):
        """Initialize the sensor."""
        self._ambient = ambient
        self._async_unsub_dispatcher_connect = None
        self._mac_address = mac_address
        self._sensor_name = sensor_name
        self._sensor_type = sensor_type
        self._state = None
        self._station_name = station_name

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            'identifiers': {
                (DOMAIN, self._mac_address)
            },
            'name': self._station_name,
            'manufacturer': 'Ambient Weather',
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{0}_{1}'.format(self._station_name, self._sensor_name)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return '{0}_{1}'.format(self._mac_address, self._sensor_name)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
