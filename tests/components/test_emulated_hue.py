import time
import json
import threading
import asyncio

import unittest
import requests

from homeassistant import bootstrap, const, core
import homeassistant.components as core_components
from homeassistant.components import emulated_hue, http, light, mqtt
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.emulated_hue import (
    HUE_API_STATE_ON, HUE_API_STATE_BRI
)

from tests.common import get_test_instance_port, get_test_home_assistant

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()
MQTT_BROKER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = "http://127.0.0.1:{}".format(BRIDGE_SERVER_PORT) + "{}"
JSON_HEADERS = {const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON}

mqtt_broker = None


def setUpModule():
    global mqtt_broker

    mqtt_broker = MQTTBroker('127.0.0.1', MQTT_BROKER_PORT)
    mqtt_broker.start()


def tearDownModule():
    global mqtt_broker

    mqtt_broker.stop()


def setup_hass_instance(emulated_hue_config):
    hass = get_test_home_assistant()

    # We need to do this to get access to homeassistant/turn_(on,off)
    core_components.setup(hass, {core.DOMAIN: {}})

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}})

    bootstrap.setup_component(hass, emulated_hue.DOMAIN, emulated_hue_config)

    return hass


def start_hass_instance(hass):
    hass.start()
    time.sleep(0.05)


class TestEmulatedHue(unittest.TestCase):
    hass = None

    @classmethod
    def setUpClass(cls):
        cls.hass = setup_hass_instance({
            emulated_hue.DOMAIN: {
                emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT
            }})

        start_hass_instance(cls.hass)

    @classmethod
    def tearDownClass(cls):
        cls.hass.stop()

    def test_description_xml(self):
        import xml.etree.ElementTree as ET

        result = requests.get(
            BRIDGE_URL_BASE.format('/description.xml'), timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('text/xml' in result.headers['content-type'])

        # Make sure the XML is parsable
        try:
            ET.fromstring(result.text)
        except:
            self.fail('description.xml is not valid XML!')

    def test_create_username(self):
        request_json = {'devicetype': 'my_device'}

        result = requests.post(
            BRIDGE_URL_BASE.format('/api'), data=json.dumps(request_json),
            timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('application/json' in result.headers['content-type'])

        resp_json = result.json()
        success_json = resp_json[0]

        self.assertTrue('success' in success_json)
        self.assertTrue('username' in success_json['success'])

    def test_valid_username_request(self):
        request_json = {'invalid_key': 'my_device'}

        result = requests.post(
            BRIDGE_URL_BASE.format('/api'), data=json.dumps(request_json),
            timeout=5)

        self.assertEqual(result.status_code, 400)


class TestEmulatedHueExposedByDefault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hass = setup_hass_instance({
            emulated_hue.DOMAIN: {
                emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
                emulated_hue.CONF_EXPOSE_BY_DEFAULT: True
            }
        })

        bootstrap.setup_component(cls.hass, mqtt.DOMAIN, {
            'mqtt': {
                'broker': '127.0.0.1',
                'port': MQTT_BROKER_PORT
            }
        })

        bootstrap.setup_component(cls.hass, light.DOMAIN, {
            'light': [
                {
                    'platform': 'mqtt',
                    'name': 'Office light',
                    'state_topic': 'office/rgb1/light/status',
                    'command_topic': 'office/rgb1/light/switch',
                    'brightness_state_topic': 'office/rgb1/brightness/status',
                    'brightness_command_topic': 'office/rgb1/brightness/set',
                    'optimistic': True
                },
                {
                    'platform': 'mqtt',
                    'name': 'Bedroom light',
                    'state_topic': 'bedroom/rgb1/light/status',
                    'command_topic': 'bedroom/rgb1/light/switch',
                    'brightness_state_topic': 'bedroom/rgb1/brightness/status',
                    'brightness_command_topic': 'bedroom/rgb1/brightness/set',
                    'optimistic': True
                },
                {
                    'platform': 'mqtt',
                    'name': 'Kitchen light',
                    'state_topic': 'kitchen/rgb1/light/status',
                    'command_topic': 'kitchen/rgb1/light/switch',
                    'brightness_state_topic': 'kitchen/rgb1/brightness/status',
                    'brightness_command_topic': 'kitchen/rgb1/brightness/set',
                    'optimistic': True
                }
            ]
        })

        start_hass_instance(cls.hass)

        # Kitchen light is explicitly excluded from being exposed
        kitchen_light_entity = cls.hass.states.get('light.kitchen_light')
        attrs = dict(kitchen_light_entity.attributes)
        attrs[emulated_hue.ATTR_EMULATED_HUE] = False
        cls.hass.states.set(
            kitchen_light_entity.entity_id, kitchen_light_entity.state,
            attributes=attrs)

    @classmethod
    def tearDownClass(cls):
        cls.hass.stop()

    def test_discover_lights(self):
        result = requests.get(
            BRIDGE_URL_BASE.format('/api/username/lights'), timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('application/json' in result.headers['content-type'])

        result_json = result.json()

        # Make sure the lights we added to the config are there
        self.assertTrue('light.office_light' in result_json)
        self.assertTrue('light.bedroom_light' in result_json)
        self.assertTrue('light.kitchen_light' not in result_json)

    def test_get_light_state(self):
        # Turn office light on and set to 127 brightness
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_ON,
            {
                const.ATTR_ENTITY_ID: 'light.office_light',
                light.ATTR_BRIGHTNESS: 127
            },
            blocking=True)

        office_json = self.perform_get_light_state('light.office_light', 200)

        self.assertEqual(office_json['state'][HUE_API_STATE_ON], True)
        self.assertEqual(office_json['state'][HUE_API_STATE_BRI], 127)

        # Turn bedroom light off
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_OFF,
            {
                const.ATTR_ENTITY_ID: 'light.bedroom_light'
            },
            blocking=True)

        bedroom_json = self.perform_get_light_state('light.bedroom_light', 200)

        self.assertEqual(bedroom_json['state'][HUE_API_STATE_ON], False)
        self.assertEqual(bedroom_json['state'][HUE_API_STATE_BRI], 0)

        # Make sure kitchen light isn't accessible
        kitchen_url = '/api/username/lights/{}'.format('light.kitchen_light')
        kitchen_result = requests.get(
            BRIDGE_URL_BASE.format(kitchen_url), timeout=5)

        self.assertEqual(kitchen_result.status_code, 404)

    def test_put_light_state(self):
        self.perform_put_test_on_office_light()

        # Turn the bedroom light on first
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_ON,
            {const.ATTR_ENTITY_ID: 'light.bedroom_light',
             light.ATTR_BRIGHTNESS: 153},
            blocking=True)

        bedroom_light = self.hass.states.get('light.bedroom_light')
        self.assertEqual(bedroom_light.state, STATE_ON)
        self.assertEqual(bedroom_light.attributes[light.ATTR_BRIGHTNESS], 153)

        # Go through the API to turn it off
        bedroom_result = self.perform_put_light_state(
            'light.bedroom_light', False)

        bedroom_result_json = bedroom_result.json()

        self.assertEqual(bedroom_result.status_code, 200)
        self.assertTrue(
            'application/json' in bedroom_result.headers['content-type'])

        self.assertEqual(len(bedroom_result_json), 1)

        # Check to make sure the state changed
        bedroom_light = self.hass.states.get('light.bedroom_light')
        self.assertEqual(bedroom_light.state, STATE_OFF)

        # Make sure we can't change the kitchen light state
        kitchen_result = self.perform_put_light_state(
            'light.kitchen_light', True)
        self.assertEqual(kitchen_result.status_code, 404)

    def test_put_with_form_urlencoded_content_type(self):
        # Needed for Alexa
        self.perform_put_test_on_office_light(
            'application/x-www-form-urlencoded')

        # Make sure we fail gracefully when we can't parse the data
        data = {'key1': 'value1', 'key2': 'value2'}
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format("light.office_light")),
            data=data)

        self.assertEqual(result.status_code, 400)

    def test_entity_not_found(self):
        result = requests.get(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}'.format("not.existant_entity")),
            timeout=5)

        self.assertEqual(result.status_code, 404)

        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format("non.existant_entity")),
            timeout=5)

        self.assertEqual(result.status_code, 404)

    def test_allowed_methods(self):
        result = requests.get(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format("light.office_light")))

        self.assertEqual(result.status_code, 405)

        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}'.format("light.office_light")),
            data={'key1': 'value1'})

        self.assertEqual(result.status_code, 405)

        result = requests.put(
            BRIDGE_URL_BASE.format('/api/username/lights'),
            data={'key1': 'value1'})

        self.assertEqual(result.status_code, 405)

    def test_proper_put_state_request(self):
        # Test proper on value parsing
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format("light.office_light")),
            data=json.dumps({HUE_API_STATE_ON: 1234}))

        self.assertEqual(result.status_code, 400)

        # Test proper brightness value parsing
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format("light.office_light")),
            data=json.dumps({
                HUE_API_STATE_ON: True,
                HUE_API_STATE_BRI: 'Hello world!'
            }))

        self.assertEqual(result.status_code, 400)

    def perform_put_test_on_office_light(self,
                                         content_type='application/json'):
        # Turn the office light off first
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_OFF,
            {const.ATTR_ENTITY_ID: 'light.office_light'},
            blocking=True)

        office_light = self.hass.states.get('light.office_light')
        self.assertEqual(office_light.state, STATE_OFF)

        # Go through the API to turn it on
        office_result = self.perform_put_light_state(
            'light.office_light', True, 56, content_type)

        office_result_json = office_result.json()

        self.assertEqual(office_result.status_code, 200)
        self.assertTrue(
            'application/json' in office_result.headers['content-type'])

        self.assertEqual(len(office_result_json), 2)

        # Check to make sure the state changed
        office_light = self.hass.states.get('light.office_light')
        self.assertEqual(office_light.state, STATE_ON)
        self.assertEqual(office_light.attributes[light.ATTR_BRIGHTNESS], 56)

    def perform_get_light_state(self, entity_id, expected_status):
        result = requests.get(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}'.format(entity_id)), timeout=5)

        self.assertEqual(result.status_code, expected_status)

        if expected_status == 200:
            self.assertTrue(
                'application/json' in result.headers['content-type'])

            return result.json()

        return None

    def perform_put_light_state(self, entity_id, is_on, brightness=None,
                                content_type='application/json'):
        url = BRIDGE_URL_BASE.format(
            '/api/username/lights/{}/state'.format(entity_id))

        req_headers = {'Content-Type': content_type}

        data = {HUE_API_STATE_ON: is_on}

        if brightness is not None:
            data[HUE_API_STATE_BRI] = brightness

        result = requests.put(
            url, data=json.dumps(data), timeout=5, headers=req_headers)
        return result


class MQTTBroker(object):
    """Encapsulates an embedded MQTT broker."""

    def __init__(self, host, port):
        """Initialize a new instance."""
        from hbmqtt.broker import Broker

        self._loop = asyncio.new_event_loop()

        hbmqtt_config = {
            'listeners': {
                'default': {
                    'max-connections': 50000,
                    'type': 'tcp',
                    'bind': '{}:{}'.format(host, port)
                }
            },
            'auth': {
                'plugins': ['auth.anonymous'],
                'allow-anonymous': True
            }
        }

        self._broker = Broker(config=hbmqtt_config, loop=self._loop)

        self._thread = threading.Thread(target=self._run_loop)
        self._started_ev = threading.Event()

    def start(self):
        """Start the broker."""
        self._thread.start()
        self._started_ev.wait()

    def stop(self):
        """Stop the broker."""
        self._loop.call_soon_threadsafe(asyncio.async, self._broker.shutdown())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._broker_coroutine())

        self._started_ev.set()

        self._loop.run_forever()
        self._loop.close()

    @asyncio.coroutine
    def _broker_coroutine(self):
        yield from self._broker.start()
