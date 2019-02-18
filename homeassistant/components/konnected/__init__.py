"""Support for Konnected devices."""
import asyncio
import hmac
import json
import logging

import voluptuous as vol

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.web import Request, Response

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.discovery import SERVICE_KONNECTED
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, HTTP_BAD_REQUEST, HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED, CONF_DEVICES, CONF_BINARY_SENSORS, CONF_SENSORS,
    CONF_SWITCHES, CONF_HOST, CONF_PORT, CONF_ID, CONF_NAME, CONF_TYPE,
    CONF_PIN, CONF_ZONE, CONF_ACCESS_TOKEN, ATTR_ENTITY_ID, ATTR_STATE,
    STATE_ON)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, dispatcher_send)
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['konnected==0.1.5']

DOMAIN = 'konnected'

CONF_ACTIVATION = 'activation'
CONF_API_HOST = 'api_host'
CONF_MOMENTARY = 'momentary'
CONF_PAUSE = 'pause'
CONF_REPEAT = 'repeat'
CONF_INVERSE = 'inverse'
CONF_BLINK = 'blink'
CONF_DISCOVERY = 'discovery'
CONF_DHT_SENSORS = 'dht_sensors'
CONF_DS18B20_SENSORS = 'ds18b20_sensors'

STATE_LOW = 'low'
STATE_HIGH = 'high'

PIN_TO_ZONE = {1: 1, 2: 2, 5: 3, 6: 4, 7: 5, 8: 'out', 9: 6}
ZONE_TO_PIN = {zone: pin for pin, zone in PIN_TO_ZONE.items()}

_BINARY_SENSOR_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_PIN, 's_pin'): vol.Any(*PIN_TO_ZONE),
        vol.Exclusive(CONF_ZONE, 's_pin'): vol.Any(*ZONE_TO_PIN),
        vol.Required(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_INVERSE, default=False): cv.boolean,
    }), cv.has_at_least_one_key(CONF_PIN, CONF_ZONE)
)

_SENSOR_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_PIN, 's_pin'): vol.Any(*PIN_TO_ZONE),
        vol.Exclusive(CONF_ZONE, 's_pin'): vol.Any(*ZONE_TO_PIN),
        vol.Required(CONF_TYPE):
            vol.All(vol.Lower, vol.In(['dht', 'ds18b20'])),
        vol.Optional(CONF_NAME): cv.string,
    }), cv.has_at_least_one_key(CONF_PIN, CONF_ZONE)
)

_SWITCH_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_PIN, 'a_pin'): vol.Any(*PIN_TO_ZONE),
        vol.Exclusive(CONF_ZONE, 'a_pin'): vol.Any(*ZONE_TO_PIN),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ACTIVATION, default=STATE_HIGH):
            vol.All(vol.Lower, vol.Any(STATE_HIGH, STATE_LOW)),
        vol.Optional(CONF_MOMENTARY):
            vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_PAUSE):
            vol.All(vol.Coerce(int), vol.Range(min=10)),
        vol.Optional(CONF_REPEAT):
            vol.All(vol.Coerce(int), vol.Range(min=-1)),
    }), cv.has_at_least_one_key(CONF_PIN, CONF_ZONE)
)

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(CONF_API_HOST): vol.Url(),
            vol.Required(CONF_DEVICES): [{
                vol.Required(CONF_ID): cv.matches_regex("[0-9a-f]{12}"),
                vol.Optional(CONF_BINARY_SENSORS): vol.All(
                    cv.ensure_list, [_BINARY_SENSOR_SCHEMA]),
                vol.Optional(CONF_SENSORS): vol.All(
                    cv.ensure_list, [_SENSOR_SCHEMA]),
                vol.Optional(CONF_SWITCHES): vol.All(
                    cv.ensure_list, [_SWITCH_SCHEMA]),
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(CONF_BLINK, default=True): cv.boolean,
                vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
            }],
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['http']

ENDPOINT_ROOT = '/api/konnected'
UPDATE_ENDPOINT = (ENDPOINT_ROOT + r'/device/{device_id:[a-zA-Z0-9]+}')
SIGNAL_SENSOR_UPDATE = 'konnected.{}.update'
SIGNAL_DS18B20_NEW = 'konnected.ds18b20.new'


async def async_setup(hass, config):
    """Set up the Konnected platform."""
    import konnected

    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    access_token = cfg.get(CONF_ACCESS_TOKEN)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {
            CONF_ACCESS_TOKEN: access_token,
            CONF_API_HOST: cfg.get(CONF_API_HOST)
        }

    def setup_device(host, port):
        """Set up a Konnected device at `host` listening on `port`."""
        discovered = DiscoveredDevice(hass, host, port)
        if discovered.is_configured:
            discovered.setup()
        else:
            _LOGGER.warning("Konnected device %s was discovered on the network"
                            " but not specified in configuration.yaml",
                            discovered.device_id)

    def device_discovered(service, info):
        """Call when a Konnected device has been discovered."""
        host = info.get(CONF_HOST)
        port = info.get(CONF_PORT)
        setup_device(host, port)

    async def manual_discovery(event):
        """Init devices on the network with manually assigned addresses."""
        specified = [dev for dev in cfg.get(CONF_DEVICES) if
                     dev.get(CONF_HOST) and dev.get(CONF_PORT)]

        while specified:
            for dev in specified:
                _LOGGER.debug("Discovering Konnected device %s at %s:%s",
                              dev.get(CONF_ID),
                              dev.get(CONF_HOST),
                              dev.get(CONF_PORT))
                try:
                    await hass.async_add_executor_job(setup_device,
                                                      dev.get(CONF_HOST),
                                                      dev.get(CONF_PORT))
                    specified.remove(dev)
                except konnected.Client.ClientError as err:
                    _LOGGER.error(err)
                    await asyncio.sleep(10)  # try again in 10 seconds

    # Initialize devices specified in the configuration on boot
    for device in cfg.get(CONF_DEVICES):
        ConfiguredDevice(hass, device, config).save_data()

    discovery.async_listen(
        hass,
        SERVICE_KONNECTED,
        device_discovered)

    hass.http.register_view(KonnectedView(access_token))
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, manual_discovery)

    return True


class ConfiguredDevice:
    """A representation of a configured Konnected device."""

    def __init__(self, hass, config, hass_config):
        """Initialize the Konnected device."""
        self.hass = hass
        self.config = config
        self.hass_config = hass_config

    @property
    def device_id(self):
        """Device id is the MAC address as string with punctuation removed."""
        return self.config.get(CONF_ID)

    def save_data(self):
        """Save the device configuration to `hass.data`."""
        binary_sensors = {}
        for entity in self.config.get(CONF_BINARY_SENSORS) or []:
            if CONF_ZONE in entity:
                pin = ZONE_TO_PIN[entity[CONF_ZONE]]
            else:
                pin = entity[CONF_PIN]

            binary_sensors[pin] = {
                CONF_TYPE: entity[CONF_TYPE],
                CONF_NAME: entity.get(CONF_NAME, 'Konnected {} Zone {}'.format(
                    self.device_id[6:], PIN_TO_ZONE[pin])),
                CONF_INVERSE: entity.get(CONF_INVERSE),
                ATTR_STATE: None
            }
            _LOGGER.debug('Set up binary_sensor %s (initial state: %s)',
                          binary_sensors[pin].get('name'),
                          binary_sensors[pin].get(ATTR_STATE))

        actuators = []
        for entity in self.config.get(CONF_SWITCHES) or []:
            if CONF_ZONE in entity:
                pin = ZONE_TO_PIN[entity[CONF_ZONE]]
            else:
                pin = entity[CONF_PIN]

            act = {
                CONF_PIN: pin,
                CONF_NAME: entity.get(
                    CONF_NAME, 'Konnected {} Actuator {}'.format(
                        self.device_id[6:], PIN_TO_ZONE[pin])),
                ATTR_STATE: None,
                CONF_ACTIVATION: entity[CONF_ACTIVATION],
                CONF_MOMENTARY: entity.get(CONF_MOMENTARY),
                CONF_PAUSE: entity.get(CONF_PAUSE),
                CONF_REPEAT: entity.get(CONF_REPEAT)}
            actuators.append(act)
            _LOGGER.debug('Set up switch %s', act)

        sensors = []
        for entity in self.config.get(CONF_SENSORS) or []:
            if CONF_ZONE in entity:
                pin = ZONE_TO_PIN[entity[CONF_ZONE]]
            else:
                pin = entity[CONF_PIN]

            sensor = {
                CONF_PIN: pin,
                CONF_NAME: entity.get(
                    CONF_NAME, 'Konnected {} Sensor {}'.format(
                        self.device_id[6:], PIN_TO_ZONE[pin])),
                CONF_TYPE: entity[CONF_TYPE],
                ATTR_STATE: None
            }
            sensors.append(sensor)
            _LOGGER.debug('Set up %s sensor %s (initial state: %s)',
                          sensor.get(CONF_TYPE),
                          sensor.get(CONF_NAME),
                          sensor.get(ATTR_STATE))

        device_data = {
            CONF_BINARY_SENSORS: binary_sensors,
            CONF_SENSORS: sensors,
            CONF_SWITCHES: actuators,
            CONF_BLINK: self.config.get(CONF_BLINK),
            CONF_DISCOVERY: self.config.get(CONF_DISCOVERY)
        }

        if CONF_DEVICES not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][CONF_DEVICES] = {}

        _LOGGER.debug('Storing data in hass.data[%s][%s][%s]: %s',
                      DOMAIN, CONF_DEVICES, self.device_id, device_data)
        self.hass.data[DOMAIN][CONF_DEVICES][self.device_id] = device_data

        discovery.load_platform(
            self.hass, 'binary_sensor', DOMAIN,
            {'device_id': self.device_id}, self.hass_config)
        discovery.load_platform(
            self.hass, 'sensor', DOMAIN,
            {'device_id': self.device_id}, self.hass_config)
        discovery.load_platform(
            self.hass, 'switch', DOMAIN,
            {'device_id': self.device_id}, self.hass_config)


class DiscoveredDevice:
    """A representation of a discovered Konnected device."""

    def __init__(self, hass, host, port):
        """Initialize the Konnected device."""
        self.hass = hass
        self.host = host
        self.port = port

        import konnected
        self.client = konnected.Client(host, str(port))
        self.status = self.client.get_status()

    def setup(self):
        """Set up a newly discovered Konnected device."""
        _LOGGER.info('Discovered Konnected device %s. Open http://%s:%s in a '
                     'web browser to view device status.',
                     self.device_id, self.host, self.port)
        self.save_data()
        self.update_initial_states()
        self.sync_device_config()

    def save_data(self):
        """Save the discovery information to `hass.data`."""
        self.stored_configuration['client'] = self.client
        self.stored_configuration['host'] = self.host
        self.stored_configuration['port'] = self.port

    @property
    def device_id(self):
        """Device id is the MAC address as string with punctuation removed."""
        return self.status['mac'].replace(':', '')

    @property
    def is_configured(self):
        """Return true if device_id is specified in the configuration."""
        return bool(self.hass.data[DOMAIN][CONF_DEVICES].get(self.device_id))

    @property
    def stored_configuration(self):
        """Return the configuration stored in `hass.data` for this device."""
        return self.hass.data[DOMAIN][CONF_DEVICES].get(self.device_id)

    def binary_sensor_configuration(self):
        """Return the configuration map for syncing binary sensors."""
        return [{'pin': p} for p in
                self.stored_configuration[CONF_BINARY_SENSORS]]

    def actuator_configuration(self):
        """Return the configuration map for syncing actuators."""
        return [{'pin': data.get(CONF_PIN),
                 'trigger': (0 if data.get(CONF_ACTIVATION) in [0, STATE_LOW]
                             else 1)}
                for data in self.stored_configuration[CONF_SWITCHES]]

    def dht_sensor_configuration(self):
        """Return the configuration map for syncing DHT sensors."""
        return [{'pin': sensor[CONF_PIN]} for sensor in
                filter(lambda s: s[CONF_TYPE] == 'dht',
                       self.stored_configuration[CONF_SENSORS])]

    def ds18b20_sensor_configuration(self):
        """Return the configuration map for syncing DS18B20 sensors."""
        return [{'pin': sensor[CONF_PIN]} for sensor in
                filter(lambda s: s[CONF_TYPE] == 'ds18b20',
                       self.stored_configuration[CONF_SENSORS])]

    def update_initial_states(self):
        """Update the initial state of each sensor from status poll."""
        for sensor_data in self.status.get('sensors'):
            sensor_config = self.stored_configuration[CONF_BINARY_SENSORS]. \
                get(sensor_data.get(CONF_PIN), {})
            entity_id = sensor_config.get(ATTR_ENTITY_ID)

            state = bool(sensor_data.get(ATTR_STATE))
            if sensor_config.get(CONF_INVERSE):
                state = not state

            dispatcher_send(
                self.hass,
                SIGNAL_SENSOR_UPDATE.format(entity_id),
                state)

    def desired_settings_payload(self):
        """Return a dict representing the desired device configuration."""
        desired_api_host = \
            self.hass.data[DOMAIN].get(CONF_API_HOST) or \
            self.hass.config.api.base_url
        desired_api_endpoint = desired_api_host + ENDPOINT_ROOT

        return {
            'sensors': self.binary_sensor_configuration(),
            'actuators': self.actuator_configuration(),
            'dht_sensors': self.dht_sensor_configuration(),
            'ds18b20_sensors': self.ds18b20_sensor_configuration(),
            'auth_token': self.hass.data[DOMAIN].get(CONF_ACCESS_TOKEN),
            'endpoint': desired_api_endpoint,
            'blink': self.stored_configuration.get(CONF_BLINK),
            'discovery': self.stored_configuration.get(CONF_DISCOVERY)
        }

    def current_settings_payload(self):
        """Return a dict of configuration currently stored on the device."""
        settings = self.status['settings']
        if not settings:
            settings = {}

        return {
            'sensors': [
                {'pin': s[CONF_PIN]} for s in self.status.get('sensors')],
            'actuators': self.status.get('actuators'),
            'dht_sensors': self.status.get(CONF_DHT_SENSORS),
            'ds18b20_sensors': self.status.get(CONF_DS18B20_SENSORS),
            'auth_token': settings.get('token'),
            'endpoint': settings.get('apiUrl'),
            'blink': settings.get(CONF_BLINK),
            'discovery': settings.get(CONF_DISCOVERY)
        }

    def sync_device_config(self):
        """Sync the new pin configuration to the Konnected device if needed."""
        _LOGGER.debug('Device %s settings payload: %s', self.device_id,
                      self.desired_settings_payload())
        if self.desired_settings_payload() != self.current_settings_payload():
            _LOGGER.info('pushing settings to device %s', self.device_id)
            self.client.put_settings(**self.desired_settings_payload())


class KonnectedView(HomeAssistantView):
    """View creates an endpoint to receive push updates from the device."""

    url = UPDATE_ENDPOINT
    extra_urls = [UPDATE_ENDPOINT + '/{pin_num}/{state}']
    name = 'api:konnected'
    requires_auth = False  # Uses access token from configuration

    def __init__(self, auth_token):
        """Initialize the view."""
        self.auth_token = auth_token

    @staticmethod
    def binary_value(state, activation):
        """Return binary value for GPIO based on state and activation."""
        if activation == STATE_HIGH:
            return 1 if state == STATE_ON else 0
        return 0 if state == STATE_ON else 1

    async def get(self, request: Request, device_id) -> Response:
        """Return the current binary state of a switch."""
        hass = request.app['hass']
        pin_num = int(request.query.get('pin'))
        data = hass.data[DOMAIN]

        device = data[CONF_DEVICES][device_id]
        if not device:
            return self.json_message(
                'Device ' + device_id + ' not configured',
                status_code=HTTP_NOT_FOUND)

        try:
            pin = next(filter(
                lambda switch: switch[CONF_PIN] == pin_num,
                device[CONF_SWITCHES]))
        except StopIteration:
            pin = None

        if not pin:
            return self.json_message(
                'Switch on pin ' + pin_num + ' not configured',
                status_code=HTTP_NOT_FOUND)

        return self.json(
            {'pin': pin_num,
             'state': self.binary_value(
                 hass.states.get(pin[ATTR_ENTITY_ID]).state,
                 pin[CONF_ACTIVATION])})

    async def put(self, request: Request, device_id,
                  pin_num=None, state=None) -> Response:
        """Receive a sensor update via PUT request and async set state."""
        hass = request.app['hass']
        data = hass.data[DOMAIN]

        try:  # Konnected 2.2.0 and above supports JSON payloads
            payload = await request.json()
            pin_num = payload['pin']
            state = payload.get('state')
        except json.decoder.JSONDecodeError:
            _LOGGER.warning(("Your Konnected device software may be out of "
                             "date. Visit https://help.konnected.io for "
                             "updating instructions."))

        auth = request.headers.get(AUTHORIZATION, None)
        if not hmac.compare_digest('Bearer {}'.format(self.auth_token), auth):
            return self.json_message(
                "unauthorized", status_code=HTTP_UNAUTHORIZED)
        pin_num = int(pin_num)
        device = data[CONF_DEVICES].get(device_id)
        if device is None:
            return self.json_message('unregistered device',
                                     status_code=HTTP_BAD_REQUEST)
        pin_data = device[CONF_BINARY_SENSORS].get(pin_num) or \
            next((s for s in device[CONF_SENSORS] if s[CONF_PIN] == pin_num),
                 None)

        if pin_data is None:
            return self.json_message('unregistered sensor/actuator',
                                     status_code=HTTP_BAD_REQUEST)

        if state:
            entity_id = pin_data.get(ATTR_ENTITY_ID)
            state = bool(int(state))
            if pin_data.get(CONF_INVERSE):
                state = not state

            async_dispatcher_send(
                hass, SIGNAL_SENSOR_UPDATE.format(entity_id), state)

        temp, humi = payload.get('temp'), payload.get('humi')
        addr = payload.get('addr')

        if addr:
            entity_id = pin_data.get(addr)
            if entity_id:
                async_dispatcher_send(
                    hass, SIGNAL_SENSOR_UPDATE.format(entity_id), temp)
            else:
                sensor_data = pin_data
                sensor_data['device_id'] = device_id
                sensor_data['temperature'] = temp
                sensor_data['addr'] = addr
                async_dispatcher_send(
                    hass, SIGNAL_DS18B20_NEW, sensor_data)
        if temp:
            entity_id = pin_data.get('temperature')
            async_dispatcher_send(
                hass, SIGNAL_SENSOR_UPDATE.format(entity_id), temp)
        if humi:
            entity_id = pin_data.get('humidity')
            async_dispatcher_send(
                hass, SIGNAL_SENSOR_UPDATE.format(entity_id), humi)

        return self.json_message('ok')
