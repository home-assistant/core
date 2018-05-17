"""
Support for Konnected devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/konnected/
"""
import logging
import hmac
import json
import voluptuous as vol

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.web import Request, Response  # NOQA

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.discovery import SERVICE_KONNECTED
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, HTTP_UNAUTHORIZED,
    CONF_DEVICES, CONF_BINARY_SENSORS, CONF_SWITCHES, CONF_HOST, CONF_PORT,
    CONF_ID, CONF_NAME, CONF_TYPE, CONF_PIN, CONF_ZONE, CONF_ACCESS_TOKEN,
    ATTR_ENTITY_ID, ATTR_STATE)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['konnected==0.1.2']

DOMAIN = 'konnected'

CONF_ACTIVATION = 'activation'
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
    }), cv.has_at_least_one_key(CONF_PIN, CONF_ZONE)
)

_SWITCH_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_PIN, 'a_pin'): vol.Any(*PIN_TO_ZONE),
        vol.Exclusive(CONF_ZONE, 'a_pin'): vol.Any(*ZONE_TO_PIN),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ACTIVATION, default=STATE_HIGH):
            vol.All(vol.Lower, vol.Any(STATE_HIGH, STATE_LOW))
    }), cv.has_at_least_one_key(CONF_PIN, CONF_ZONE)
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Required(CONF_DEVICES): [{
                vol.Required(CONF_ID): cv.string,
                vol.Optional(CONF_BINARY_SENSORS): vol.All(
                    cv.ensure_list, [_BINARY_SENSOR_SCHEMA]),
                vol.Optional(CONF_SWITCHES): vol.All(
                    cv.ensure_list, [_SWITCH_SCHEMA]),
            }],
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['http', 'discovery']

ENDPOINT_ROOT = '/api/konnected'
UPDATE_ENDPOINT = (ENDPOINT_ROOT + r'/device/{device_id:[a-zA-Z0-9]+}')
SIGNAL_SENSOR_UPDATE = 'konnected.{}.update'


async def async_setup(hass, config):
    """Set up the Konnected platform."""
    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    access_token = cfg.get(CONF_ACCESS_TOKEN)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {CONF_ACCESS_TOKEN: access_token}

    def device_discovered(service, info):
        """Call when a Konnected device has been discovered."""
        _LOGGER.debug("Discovered a new Konnected device: %s", info)
        host = info.get(CONF_HOST)
        port = info.get(CONF_PORT)

        device = KonnectedDevice(hass, host, port, cfg)
        device.setup()

    discovery.async_listen(
        hass,
        SERVICE_KONNECTED,
        device_discovered)

    hass.http.register_view(KonnectedView(access_token))

    return True


class KonnectedDevice(object):
    """A representation of a single Konnected device."""

    def __init__(self, hass, host, port, config):
        """Initialize the Konnected device."""
        self.hass = hass
        self.host = host
        self.port = port
        self.user_config = config

        import konnected
        self.client = konnected.Client(host, str(port))
        self.status = self.client.get_status()
        _LOGGER.info('Initialized Konnected device %s', self.device_id)

    def setup(self):
        """Set up a newly discovered Konnected device."""
        user_config = self.config()
        if user_config:
            _LOGGER.debug('Configuring Konnected device %s', self.device_id)
            self.save_data()
            self.sync_device_config()
            discovery.load_platform(
                self.hass, 'binary_sensor',
                DOMAIN, {'device_id': self.device_id})
            discovery.load_platform(
                self.hass, 'switch', DOMAIN,
                {'device_id': self.device_id})

    @property
    def device_id(self):
        """Device id is the MAC address as string with punctuation removed."""
        return self.status['mac'].replace(':', '')

    def config(self):
        """Return an object representing the user defined configuration."""
        device_id = self.device_id
        valid_keys = [device_id, device_id.upper(),
                      device_id[6:], device_id.upper()[6:]]
        configured_devices = self.user_config[CONF_DEVICES]
        return next((device for device in
                     configured_devices if device[CONF_ID] in valid_keys),
                    None)

    def save_data(self):
        """Save the device configuration to `hass.data`."""
        sensors = {}
        for entity in self.config().get(CONF_BINARY_SENSORS) or []:
            if CONF_ZONE in entity:
                pin = ZONE_TO_PIN[entity[CONF_ZONE]]
            else:
                pin = entity[CONF_PIN]

            sensor_status = next((sensor for sensor in
                                  self.status.get('sensors') if
                                  sensor.get(CONF_PIN) == pin), {})
            if sensor_status.get(ATTR_STATE):
                initial_state = bool(int(sensor_status.get(ATTR_STATE)))
            else:
                initial_state = None

            sensors[pin] = {
                CONF_TYPE: entity[CONF_TYPE],
                CONF_NAME: entity.get(CONF_NAME, 'Konnected {} Zone {}'.format(
                    self.device_id[6:], PIN_TO_ZONE[pin])),
                ATTR_STATE: initial_state
            }
            _LOGGER.debug('Set up sensor %s (initial state: %s)',
                          sensors[pin].get('name'),
                          sensors[pin].get(ATTR_STATE))

        actuators = {}
        for entity in self.config().get(CONF_SWITCHES) or []:
            if 'zone' in entity:
                pin = ZONE_TO_PIN[entity['zone']]
            else:
                pin = entity['pin']

            actuator_status = next((actuator for actuator in
                                    self.status.get('actuators') if
                                    actuator.get('pin') == pin), {})
            if actuator_status.get(ATTR_STATE):
                initial_state = bool(int(actuator_status.get(ATTR_STATE)))
            else:
                initial_state = None

            actuators[pin] = {
                CONF_NAME: entity.get(
                    CONF_NAME, 'Konnected {} Actuator {}'.format(
                        self.device_id[6:], PIN_TO_ZONE[pin])),
                ATTR_STATE: initial_state,
                CONF_ACTIVATION: entity[CONF_ACTIVATION],
            }
            _LOGGER.debug('Set up actuator %s (initial state: %s)',
                          actuators[pin].get(CONF_NAME),
                          actuators[pin].get(ATTR_STATE))

        device_data = {
            'client': self.client,
            CONF_BINARY_SENSORS: sensors,
            CONF_SWITCHES: actuators,
            CONF_HOST: self.host,
            CONF_PORT: self.port,
        }

        if CONF_DEVICES not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][CONF_DEVICES] = {}

        _LOGGER.debug('Storing data in hass.data[konnected]: %s', device_data)
        self.hass.data[DOMAIN][CONF_DEVICES][self.device_id] = device_data

    @property
    def stored_configuration(self):
        """Return the configuration stored in `hass.data` for this device."""
        return self.hass.data[DOMAIN][CONF_DEVICES][self.device_id]

    def sensor_configuration(self):
        """Return the configuration map for syncing sensors."""
        return [{'pin': p} for p in
                self.stored_configuration[CONF_BINARY_SENSORS]]

    def actuator_configuration(self):
        """Return the configuration map for syncing actuators."""
        return [{'pin': p,
                 'trigger': (0 if data.get(CONF_ACTIVATION) in [0, STATE_LOW]
                             else 1)}
                for p, data in
                self.stored_configuration[CONF_SWITCHES].items()]

    def sync_device_config(self):
        """Sync the new pin configuration to the Konnected device."""
        desired_sensor_configuration = self.sensor_configuration()
        current_sensor_configuration = [
            {'pin': s[CONF_PIN]} for s in self.status.get('sensors')]
        _LOGGER.debug('%s: desired sensor config: %s', self.device_id,
                      desired_sensor_configuration)
        _LOGGER.debug('%s: current sensor config: %s', self.device_id,
                      current_sensor_configuration)

        desired_actuator_config = self.actuator_configuration()
        current_actuator_config = self.status.get('actuators')
        _LOGGER.debug('%s: desired actuator config: %s', self.device_id,
                      desired_actuator_config)
        _LOGGER.debug('%s: current actuator config: %s', self.device_id,
                      current_actuator_config)

        if (desired_sensor_configuration != current_sensor_configuration) or \
                (current_actuator_config != desired_actuator_config):
            _LOGGER.debug('pushing settings to device %s', self.device_id)
            self.client.put_settings(
                desired_sensor_configuration,
                desired_actuator_config,
                self.hass.data[DOMAIN].get(CONF_ACCESS_TOKEN),
                self.hass.config.api.base_url + ENDPOINT_ROOT
            )


class KonnectedView(HomeAssistantView):
    """View creates an endpoint to receive push updates from the device."""

    url = UPDATE_ENDPOINT
    extra_urls = [UPDATE_ENDPOINT + '/{pin_num}/{state}']
    name = 'api:konnected'
    requires_auth = False  # Uses access token from configuration

    def __init__(self, auth_token):
        """Initialize the view."""
        self.auth_token = auth_token

    async def put(self, request: Request, device_id,
                  pin_num=None, state=None) -> Response:
        """Receive a sensor update via PUT request and async set state."""
        hass = request.app['hass']
        data = hass.data[DOMAIN]

        try:  # Konnected 2.2.0 and above supports JSON payloads
            payload = await request.json()
            pin_num = payload['pin']
            state = payload['state']
        except json.decoder.JSONDecodeError:
            _LOGGER.warning(("Your Konnected device software may be out of "
                             "date. Visit https://help.konnected.io for "
                             "updating instructions."))

        auth = request.headers.get(AUTHORIZATION, None)
        if not hmac.compare_digest('Bearer {}'.format(self.auth_token), auth):
            return self.json_message(
                "unauthorized", status_code=HTTP_UNAUTHORIZED)
        pin_num = int(pin_num)
        state = bool(int(state))
        device = data[CONF_DEVICES].get(device_id)
        if device is None:
            return self.json_message('unregistered device',
                                     status_code=HTTP_BAD_REQUEST)
        pin_data = device[CONF_BINARY_SENSORS].get(pin_num) or \
            device[CONF_SWITCHES].get(pin_num)

        if pin_data is None:
            return self.json_message('unregistered sensor/actuator',
                                     status_code=HTTP_BAD_REQUEST)

        entity_id = pin_data.get(ATTR_ENTITY_ID)
        if entity_id is None:
            return self.json_message('uninitialized sensor/actuator',
                                     status_code=HTTP_INTERNAL_SERVER_ERROR)

        async_dispatcher_send(
            hass, SIGNAL_SENSOR_UPDATE.format(entity_id), state)
        return self.json_message('ok')
