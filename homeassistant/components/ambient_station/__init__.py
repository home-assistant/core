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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .config_flow import configured_instances
from .const import (
    ATTR_LAST_DATA, CONF_APP_KEY, DATA_CLIENT, DOMAIN, TOPIC_UPDATE)

REQUIREMENTS = ['aioambient==0.1.0']
_LOGGER = logging.getLogger(__name__)

DEFAULT_SOCKET_MIN_RETRY = 15

SENSOR_TYPES = {
    '24hourrainin': ('24 Hr Rain', 'in'),
    'baromabsin': ('Abs Pressure', 'inHg'),
    'baromrelin': ('Rel Pressure', 'inHg'),
    'battout': ('Battery', ''),
    'co2': ('co2', 'ppm'),
    'dailyrainin': ('Daily Rain', 'in'),
    'dewPoint': ('Dew Point', '°F'),
    'eventrainin': ('Event Rain', 'in'),
    'feelsLike': ('Feels Like', '°F'),
    'hourlyrainin': ('Hourly Rain Rate', 'in/hr'),
    'humidity': ('Humidity', '%'),
    'humidityin': ('Humidity In', '%'),
    'lastRain': ('Last Rain', ''),
    'maxdailygust': ('Max Gust', 'mph'),
    'monthlyrainin': ('Monthly Rain', 'in'),
    'solarradiation': ('Solar Rad', 'W/m^2'),
    'tempf': ('Temp', '°F'),
    'tempinf': ('Inside Temp', '°F'),
    'totalrainin': ('Lifetime Rain', 'in'),
    'uv': ('uv', 'Index'),
    'weeklyrainin': ('Weekly Rain', 'in'),
    'winddir': ('Wind Dir', '°'),
    'winddir_avg10m': ('Wind Dir Avg 10m', '°'),
    'winddir_avg2m': ('Wind Dir Avg 2m', 'mph'),
    'windgustdir': ('Gust Dir', '°'),
    'windgustmph': ('Wind Gust', 'mph'),
    'windspdmph_avg10m': ('Wind Avg 10m', 'mph'),
    'windspdmph_avg2m': ('Wind Avg 2m', 'mph'),
    'windspeedmph': ('Wind Speed', 'mph'),
    'yearlyrainin': ('Yearly Rain', 'in'),
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN:
        vol.Schema({
            vol.Required(CONF_APP_KEY):
                cv.string,
            vol.Required(CONF_API_KEY):
                cv.string,
            vol.Optional(
                CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
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
            hass,
            config_entry,
            Client(
                config_entry.data[CONF_API_KEY],
                config_entry.data[CONF_APP_KEY], session),
            config_entry.data.get(
                CONF_MONITORED_CONDITIONS, list(SENSOR_TYPES)))
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

    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'sensor')

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

                self.stations[station['macAddress']] = {
                    ATTR_LAST_DATA: station['lastData'],
                    ATTR_LOCATION: station['info']['location'],
                    ATTR_NAME: station['info']['name'],
                }

                self._hass.async_create_task(
                    self._hass.config_entries.async_forward_entry_setup(
                        self._config_entry, 'sensor'))

                self._ws_reconnect_delay = DEFAULT_SOCKET_MIN_RETRY

        self.client.websocket.on_connect(on_connect)
        self.client.websocket.on_data(on_data)
        self.client.websocket.on_disconnect(on_disconnect)
        self.client.websocket.on_subscribed(on_subscribed)

        try:
            await self.client.websocket.connect()
        except WebsocketError as err:
            _LOGGER.error("Error with the websocket connection: %s", err)

            self._ws_reconnect_delay = min(
                2 * self._ws_reconnect_delay, 480)

            async_call_later(
                self._hass, self._ws_reconnect_delay, self.ws_connect)

    async def ws_disconnect(self):
        """Disconnect from the websocket."""
        await self.client.websocket.disconnect()
