"""The tests for the Scene component."""
import io
import unittest

from homeassistant.setup import setup_component
from homeassistant import loader
from homeassistant.components import light, scene
from homeassistant.util import yaml

from tests.common import get_test_home_assistant
from tests.components.light import common as common_light
from tests.components.scene import common


class TestScene(unittest.TestCase):
    """Test the scene component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        test_light = loader.get_component(self.hass, 'light.test')
        test_light.init()

        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {'platform': 'test'}
        })

        self.light_1, self.light_2 = test_light.DEVICES[0:2]

        common_light.turn_off(
            self.hass, [self.light_1.entity_id, self.light_2.entity_id])

        self.hass.block_till_done()

        assert not self.light_1.is_on
        assert not self.light_2.is_on

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_config_yaml_alias_anchor(self):
        """Test the usage of YAML aliases and anchors.

        The following test scene configuration is equivalent to:

        scene:
          - name: test
            entities:
              light_1: &light_1_state
                state: 'on'
                brightness: 100
              light_2: *light_1_state

        When encountering a YAML alias/anchor, the PyYAML parser will use a
        reference to the original dictionary, instead of creating a copy, so
        care needs to be taken to not modify the original.
        """
        entity_state = {
            'state': 'on',
            'brightness': 100,
        }
        assert setup_component(self.hass, scene.DOMAIN, {
            'scene': [{
                'name': 'test',
                'entities': {
                    self.light_1.entity_id: entity_state,
                    self.light_2.entity_id: entity_state,
                }
            }]
        })

        common.activate(self.hass, 'scene.test')
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert 100 == self.light_1.last_call('turn_on')[1].get('brightness')
        assert 100 == self.light_2.last_call('turn_on')[1].get('brightness')

    def test_config_yaml_bool(self):
        """Test parsing of booleans in yaml config."""
        config = (
            'scene:\n'
            '  - name: test\n'
            '    entities:\n'
            '      {0}: on\n'
            '      {1}:\n'
            '        state: on\n'
            '        brightness: 100\n').format(
                self.light_1.entity_id, self.light_2.entity_id)

        with io.StringIO(config) as file:
            doc = yaml.yaml.safe_load(file)

        assert setup_component(self.hass, scene.DOMAIN, doc)
        common.activate(self.hass, 'scene.test')
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert 100 == self.light_2.last_call('turn_on')[1].get('brightness')

    def test_activate_scene(self):
        """Test active scene."""
        assert setup_component(self.hass, scene.DOMAIN, {
            'scene': [{
                'name': 'test',
                'entities': {
                    self.light_1.entity_id: 'on',
                    self.light_2.entity_id: {
                        'state': 'on',
                        'brightness': 100,
                    }
                }
            }]
        })

        common.activate(self.hass, 'scene.test')
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert 100 == self.light_2.last_call('turn_on')[1].get('brightness')
