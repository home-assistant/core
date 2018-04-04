"""
Support for Konnected devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/konnected/
"""
import asyncio
import logging
import voluptuous as vol

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.web import Request, Response  # NOQA

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.discovery import SERVICE_KONNECTED
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, HTTP_UNAUTHORIZED)
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['konnected==0.1.2']

DOMAIN = 'konnected'

PIN_TO_ZONE = {1: 1, 2: 2, 5: 3, 6: 4, 7: 5, 8: 'out', 9: 6}
ZONE_TO_PIN = {zone: pin for pin, zone in PIN_TO_ZONE.items()}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            'auth_token': str,
            vol.Optional('home_assistant_url'): str,
            'devices': [{
                vol.Required('id', default=''): vol.Coerce(str),
                'sensors': [{
                    vol.Exclusive('pin', 's_pin'): vol.Any(*PIN_TO_ZONE),
                    vol.Exclusive('zone', 's_pin'): vol.Any(*ZONE_TO_PIN),
                    vol.Required('type', default='motion'):
                        DEVICE_CLASSES_SCHEMA,
                    vol.Optional('name'): str,
                }],
                'actuators': [{
                    vol.Exclusive('pin', 'a_pin'): vol.Any(*PIN_TO_ZONE),
                    vol.Exclusive('zone', 'a_pin'): vol.Any(*ZONE_TO_PIN),
                    vol.Optional('name'): str,
                    vol.Required('activation', default='high'):
                        vol.All(vol.Lower, vol.Any('high', 'low'))
                }],
            }],
        },
    },
    extra=vol.ALLOW_EXTRA,
)

DEPENDENCIES = ['http']

ENDPOINT_ROOT = '/api/konnected'
UPDATE_ENDPOINT = (
    ENDPOINT_ROOT +
    r'/device/{device_id:[a-zA-Z0-9]+}/{pin_num:[0-9]}/{state:[01]}')


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Konnected platform."""
    cfg = config.get(DOMAIN)
    if cfg is None:
        cfg = {}

    auth_token = cfg.get('auth_token') or 'supersecret'
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {'auth_token': auth_token}

    @asyncio.coroutine
    def async_device_discovered(service, info):
        """Call when a Konnected device has been discovered."""
        _LOGGER.info("Discovered a new Konnected device: %s", info)
        host = info.get('host')
        port = info.get('port')

        device = KonnectedDevice(hass, host, port, cfg)
        device.setup()

    discovery.async_listen(
        hass,
        SERVICE_KONNECTED,
        async_device_discovered)

    hass.http.register_view(KonnectedView(auth_token))

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
            _LOGGER.info('Configuring Konnected device %s', self.device_id)
            self.save_data()
            self.sync_device()
            self.hass.async_add_job(
                discovery.async_load_platform(
                    self.hass, 'binary_sensor',
                    DOMAIN, {'device_id': self.device_id}))
            self.hass.async_add_job(
                discovery.async_load_platform(
                    self.hass, 'switch', DOMAIN,
                    {'device_id': self.device_id}))

    @property
    def device_id(self):
        """Device id is the MAC address as string with punctuation removed."""
        return self.status['mac'].replace(':', '')

    def config(self):
        """Return an object representing the user defined configuration."""
        device_id = self.device_id
        valid_keys = [device_id, device_id.upper(),
                      device_id[6:], device_id.upper()[6:]]
        configured_devices = self.user_config['devices']
        return next((device for device in
                     configured_devices if device['id'] in valid_keys), None)

    def save_data(self):
        """Save the device configuration to `hass.data`.

        TODO: This can probably be refactored and tidied up.
        """
        sensors = {}
        for entity in self.config().get('sensors') or []:
            if 'zone' in entity:
                pin = ZONE_TO_PIN[entity['zone']]
            else:
                pin = entity['pin']

            sensor_status = next((sensor for sensor in
                                  self.status.get('sensors') if
                                  sensor.get('pin') == pin), {})
            if sensor_status.get('state'):
                initial_state = bool(int(sensor_status.get('state')))
            else:
                initial_state = None

            sensors[pin] = {
                'type': entity['type'],
                'name': entity.get('name', 'Konnected {} Zone {}'.format(
                    self.device_id[6:], PIN_TO_ZONE[pin])),
                'state': initial_state
            }
            _LOGGER.info('Set up sensor %s (initial state: %s)',
                         sensors[pin].get('name'), sensors[pin].get('state'))

        actuators = {}
        for entity in self.config().get('actuators') or []:
            if 'zone' in entity:
                pin = ZONE_TO_PIN[entity['zone']]
            else:
                pin = entity['pin']

            actuator_status = next((actuator for actuator in
                                    self.status.get('actuators') if
                                    actuator.get('pin') == pin), {})
            if actuator_status.get('state'):
                initial_state = bool(int(actuator_status.get('state')))
            else:
                initial_state = None

            actuators[pin] = {
                'name': entity.get('name', 'Konnected {} Actuator {}'.format(
                    self.device_id[6:], PIN_TO_ZONE[pin])),
                'state': initial_state,
                'activation': entity['activation'],
            }
            _LOGGER.info('Set up actuator %s (initial state: %s)',
                         actuators[pin].get('name'),
                         actuators[pin].get('state'))

        device_data = {
            'client': self.client,
            'sensors': sensors,
            'actuators': actuators,
            'host': self.host,
            'port': self.port,
        }

        if 'devices' not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN]['devices'] = {}

        _LOGGER.info('Storing data in hass.data[konnected]: %s', device_data)
        self.hass.data[DOMAIN]['devices'][self.device_id] = device_data

    @property
    def stored_configuration(self):
        """Return the configuration stored in `hass.data` for this device."""
        return self.hass.data[DOMAIN]['devices'][self.device_id]

    def sensor_configuration(self):
        """Return the configuration map for syncing sensors."""
        return [{'pin': p} for p in
                self.stored_configuration['sensors'].keys()]

    def actuator_configuration(self):
        """Return the configuration map for syncing actuators."""
        return [{'pin': p,
                 'trigger': (0 if data.get('activation') in [0, 'low'] else 1)}
                for p, data in
                self.stored_configuration['actuators'].items()]

    def sync_device(self):
        """Sync the new pin configuration to the Konnected device."""
        desired_sensor_configuration = self.sensor_configuration()
        current_sensor_configuration = [
            {'pin': s['pin']} for s in self.status.get('sensors')]
        _LOGGER.info('%s: desired sensor config: %s', self.device_id,
                     desired_sensor_configuration)
        _LOGGER.info('%s: current sensor config: %s', self.device_id,
                     current_sensor_configuration)

        desired_actuator_config = self.actuator_configuration()
        current_actuator_config = self.status.get('actuators')
        _LOGGER.info('%s: desired actuator config: %s', self.device_id,
                     desired_actuator_config)
        _LOGGER.info('%s: current actuator config: %s', self.device_id,
                     current_actuator_config)

        if (desired_sensor_configuration != current_sensor_configuration) or \
                (current_actuator_config != desired_actuator_config):
            _LOGGER.info('pushing settings to device %s', self.device_id)
            self.client.put_settings(
                desired_sensor_configuration,
                desired_actuator_config,
                self.hass.data[DOMAIN].get('auth_token'),
                self.hass.config.api.base_url + ENDPOINT_ROOT
            )


class KonnectedView(HomeAssistantView):
    """View creates an endpoint to receive push updates from the device."""

    url = UPDATE_ENDPOINT
    name = 'api:konnected'
    requires_auth = False  # Uses access token from configuration

    def __init__(self, auth_token):
        """Initialize the view."""
        self.auth_token = auth_token

    @asyncio.coroutine
    def put(self, request: Request, device_id, pin_num, state) -> Response:
        """Receive a sensor update via PUT request and async set state."""
        hass = request.app['hass']
        data = hass.data[DOMAIN]

        auth = request.headers.get(AUTHORIZATION, None)
        if 'Bearer {}'.format(self.auth_token) != auth:
            return self.json_message(
                "unauthorized", status_code=HTTP_UNAUTHORIZED)
        pin_num = int(pin_num)
        state = bool(int(state))
        device = data['devices'].get(device_id)
        if device is None:
            return self.json_message('unregistered device',
                                     status_code=HTTP_BAD_REQUEST)
        pin_data = device['sensors'].get(pin_num) or \
            device['actuators'].get(pin_num)

        if pin_data is None:
            return self.json_message('unregistered sensor/actuator',
                                     status_code=HTTP_BAD_REQUEST)
        entity = pin_data.get('entity')
        if entity is None:
            return self.json_message('uninitialized sensor/actuator',
                                     status_code=HTTP_INTERNAL_SERVER_ERROR)

        yield from entity.async_set_state(state)
        return self.json_message('ok')
