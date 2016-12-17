"""The tests for the emulated Hue component."""
import json

import unittest
from unittest.mock import patch
import requests

from homeassistant import bootstrap, const, core
import homeassistant.components as core_components
from homeassistant.components import (
    emulated_hue, http, light, script, media_player
)
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.emulated_hue.hue_api import (
    HUE_API_STATE_ON, HUE_API_STATE_BRI)
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import get_test_instance_port, get_test_home_assistant

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = 'http://127.0.0.1:{}'.format(BRIDGE_SERVER_PORT) + '{}'
JSON_HEADERS = {const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON}


class TestEmulatedHueExposedByDefault(unittest.TestCase):
    """Test class for emulated hue component."""

    @classmethod
    def setUpClass(cls):
        """Setup the class."""
        cls.hass = hass = get_test_home_assistant()

        # We need to do this to get access to homeassistant/turn_(on,off)
        run_coroutine_threadsafe(
            core_components.async_setup(hass, {core.DOMAIN: {}}), hass.loop
        ).result()

        bootstrap.setup_component(
            hass, http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}})

        with patch('homeassistant.components'
                   '.emulated_hue.UPNPResponderThread'):
            bootstrap.setup_component(hass, emulated_hue.DOMAIN, {
                emulated_hue.DOMAIN: {
                    emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
                    emulated_hue.CONF_EXPOSE_BY_DEFAULT: True
                }
            })

        bootstrap.setup_component(cls.hass, light.DOMAIN, {
            'light': [
                {
                    'platform': 'demo',
                }
            ]
        })

        bootstrap.setup_component(cls.hass, script.DOMAIN, {
            'script': {
                'set_kitchen_light': {
                    'sequence': [
                        {
                            'service_template':
                                "light.turn_{{ requested_state }}",
                            'data_template': {
                                'entity_id': 'light.kitchen_lights',
                                'brightness': "{{ requested_level }}"
                                }
                        }
                    ]
                }
            }
        })

        bootstrap.setup_component(cls.hass, media_player.DOMAIN, {
            'media_player': [
                {
                    'platform': 'demo',
                }
            ]
        })

        cls.hass.start()

        # Kitchen light is explicitly excluded from being exposed
        kitchen_light_entity = cls.hass.states.get('light.kitchen_lights')
        attrs = dict(kitchen_light_entity.attributes)
        attrs[emulated_hue.ATTR_EMULATED_HUE] = False
        cls.hass.states.set(
            kitchen_light_entity.entity_id, kitchen_light_entity.state,
            attributes=attrs)

        # Expose the script
        script_entity = cls.hass.states.get('script.set_kitchen_light')
        attrs = dict(script_entity.attributes)
        attrs[emulated_hue.ATTR_EMULATED_HUE] = True
        cls.hass.states.set(
            script_entity.entity_id, script_entity.state, attributes=attrs
        )

    @classmethod
    def tearDownClass(cls):
        """Stop the class."""
        cls.hass.stop()

    def test_discover_lights(self):
        """Test the discovery of lights."""
        result = requests.get(
            BRIDGE_URL_BASE.format('/api/username/lights'), timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('application/json' in result.headers['content-type'])

        result_json = result.json()

        # Make sure the lights we added to the config are there
        self.assertTrue('light.ceiling_lights' in result_json)
        self.assertTrue('light.bed_light' in result_json)
        self.assertTrue('script.set_kitchen_light' in result_json)
        self.assertTrue('light.kitchen_lights' not in result_json)
        self.assertTrue('media_player.living_room' in result_json)
        self.assertTrue('media_player.bedroom' in result_json)
        self.assertTrue('media_player.walkman' in result_json)
        self.assertTrue('media_player.lounge_room' in result_json)

    def test_get_light_state(self):
        """Test the getting of light state."""
        # Turn office light on and set to 127 brightness
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_ON,
            {
                const.ATTR_ENTITY_ID: 'light.ceiling_lights',
                light.ATTR_BRIGHTNESS: 127
            },
            blocking=True)

        office_json = self.perform_get_light_state('light.ceiling_lights', 200)

        self.assertEqual(office_json['state'][HUE_API_STATE_ON], True)
        self.assertEqual(office_json['state'][HUE_API_STATE_BRI], 127)

        # Check all lights view
        result = requests.get(
            BRIDGE_URL_BASE.format('/api/username/lights'), timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('application/json' in result.headers['content-type'])

        result_json = result.json()

        self.assertTrue('light.ceiling_lights' in result_json)
        self.assertEqual(
            result_json['light.ceiling_lights']['state'][HUE_API_STATE_BRI],
            127,
        )

        # Turn bedroom light off
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_OFF,
            {
                const.ATTR_ENTITY_ID: 'light.bed_light'
            },
            blocking=True)

        bedroom_json = self.perform_get_light_state('light.bed_light', 200)

        self.assertEqual(bedroom_json['state'][HUE_API_STATE_ON], False)
        self.assertEqual(bedroom_json['state'][HUE_API_STATE_BRI], 0)

        # Make sure kitchen light isn't accessible
        kitchen_url = '/api/username/lights/{}'.format('light.kitchen_lights')
        kitchen_result = requests.get(
            BRIDGE_URL_BASE.format(kitchen_url), timeout=5)

        self.assertEqual(kitchen_result.status_code, 404)

    def test_put_light_state(self):
        """Test the seeting of light states."""
        self.perform_put_test_on_ceiling_lights()

        # Turn the bedroom light on first
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_ON,
            {const.ATTR_ENTITY_ID: 'light.bed_light',
             light.ATTR_BRIGHTNESS: 153},
            blocking=True)

        bed_light = self.hass.states.get('light.bed_light')
        self.assertEqual(bed_light.state, STATE_ON)
        self.assertEqual(bed_light.attributes[light.ATTR_BRIGHTNESS], 153)

        # Go through the API to turn it off
        bedroom_result = self.perform_put_light_state(
            'light.bed_light', False)

        bedroom_result_json = bedroom_result.json()

        self.assertEqual(bedroom_result.status_code, 200)
        self.assertTrue(
            'application/json' in bedroom_result.headers['content-type'])

        self.assertEqual(len(bedroom_result_json), 1)

        # Check to make sure the state changed
        bed_light = self.hass.states.get('light.bed_light')
        self.assertEqual(bed_light.state, STATE_OFF)

        # Make sure we can't change the kitchen light state
        kitchen_result = self.perform_put_light_state(
            'light.kitchen_light', True)
        self.assertEqual(kitchen_result.status_code, 404)

    def test_put_light_state_script(self):
        """Test the setting of script variables."""
        # Turn the kitchen light off first
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_OFF,
            {const.ATTR_ENTITY_ID: 'light.kitchen_lights'},
            blocking=True)

        # Emulated hue converts 0-100% to 0-255.
        level = 23
        brightness = round(level * 255 / 100)

        script_result = self.perform_put_light_state(
            'script.set_kitchen_light', True, brightness)

        script_result_json = script_result.json()

        self.assertEqual(script_result.status_code, 200)
        self.assertEqual(len(script_result_json), 2)

        kitchen_light = self.hass.states.get('light.kitchen_lights')
        self.assertEqual(kitchen_light.state, 'on')
        self.assertEqual(
            kitchen_light.attributes[light.ATTR_BRIGHTNESS],
            level)

    def test_put_light_state_media_player(self):
        """Test turning on media player and setting volume."""
        # Turn the music player off first
        self.hass.services.call(
            media_player.DOMAIN, const.SERVICE_TURN_OFF,
            {const.ATTR_ENTITY_ID: 'media_player.walkman'},
            blocking=True)

        # Emulated hue converts 0.0-1.0 to 0-255.
        level = 0.25
        brightness = round(level * 255)

        mp_result = self.perform_put_light_state(
            'media_player.walkman', True, brightness)

        mp_result_json = mp_result.json()

        self.assertEqual(mp_result.status_code, 200)
        self.assertEqual(len(mp_result_json), 2)

        walkman = self.hass.states.get('media_player.walkman')
        self.assertEqual(walkman.state, 'playing')
        self.assertEqual(
            walkman.attributes[media_player.ATTR_MEDIA_VOLUME_LEVEL],
            level)

    # pylint: disable=invalid-name
    def test_put_with_form_urlencoded_content_type(self):
        """Test the form with urlencoded content."""
        # Needed for Alexa
        self.perform_put_test_on_ceiling_lights(
            'application/x-www-form-urlencoded')

        # Make sure we fail gracefully when we can't parse the data
        data = {'key1': 'value1', 'key2': 'value2'}
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format(
                    'light.ceiling_lights')), data=data)

        self.assertEqual(result.status_code, 400)

    def test_entity_not_found(self):
        """Test for entity which are not found."""
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
        """Test the allowed methods."""
        result = requests.get(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format(
                    "light.ceiling_lights")))

        self.assertEqual(result.status_code, 405)

        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}'.format("light.ceiling_lights")),
            data={'key1': 'value1'})

        self.assertEqual(result.status_code, 405)

        result = requests.put(
            BRIDGE_URL_BASE.format('/api/username/lights'),
            data={'key1': 'value1'})

        self.assertEqual(result.status_code, 405)

    def test_proper_put_state_request(self):
        """Test the request to set the state."""
        # Test proper on value parsing
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format(
                    'light.ceiling_lights')),
            data=json.dumps({HUE_API_STATE_ON: 1234}))

        self.assertEqual(result.status_code, 400)

        # Test proper brightness value parsing
        result = requests.put(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}/state'.format(
                    'light.ceiling_lights')), data=json.dumps({
                        HUE_API_STATE_ON: True,
                        HUE_API_STATE_BRI: 'Hello world!'
                    }))

        self.assertEqual(result.status_code, 400)

    # pylint: disable=invalid-name
    def perform_put_test_on_ceiling_lights(self,
                                           content_type='application/json'):
        """Test the setting of a light."""
        # Turn the office light off first
        self.hass.services.call(
            light.DOMAIN, const.SERVICE_TURN_OFF,
            {const.ATTR_ENTITY_ID: 'light.ceiling_lights'},
            blocking=True)

        ceiling_lights = self.hass.states.get('light.ceiling_lights')
        self.assertEqual(ceiling_lights.state, STATE_OFF)

        # Go through the API to turn it on
        office_result = self.perform_put_light_state(
            'light.ceiling_lights', True, 56, content_type)

        office_result_json = office_result.json()

        self.assertEqual(office_result.status_code, 200)
        self.assertTrue(
            'application/json' in office_result.headers['content-type'])

        self.assertEqual(len(office_result_json), 2)

        # Check to make sure the state changed
        ceiling_lights = self.hass.states.get('light.ceiling_lights')
        self.assertEqual(ceiling_lights.state, STATE_ON)
        self.assertEqual(ceiling_lights.attributes[light.ATTR_BRIGHTNESS], 56)

    def perform_get_light_state(self, entity_id, expected_status):
        """Test the gettting of a light state."""
        result = requests.get(
            BRIDGE_URL_BASE.format(
                '/api/username/lights/{}'.format(entity_id)), timeout=5)

        self.assertEqual(result.status_code, expected_status)

        if expected_status == 200:
            self.assertTrue(
                'application/json' in result.headers['content-type'])

            return result.json()

        return None

    # pylint: disable=no-self-use
    def perform_put_light_state(self, entity_id, is_on, brightness=None,
                                content_type='application/json'):
        """Test the setting of a light state."""
        url = BRIDGE_URL_BASE.format(
            '/api/username/lights/{}/state'.format(entity_id))

        req_headers = {'Content-Type': content_type}

        data = {HUE_API_STATE_ON: is_on}

        if brightness is not None:
            data[HUE_API_STATE_BRI] = brightness

        result = requests.put(
            url, data=json.dumps(data), timeout=5, headers=req_headers)

        # Wait until state change is complete before continuing
        self.hass.block_till_done()

        return result
