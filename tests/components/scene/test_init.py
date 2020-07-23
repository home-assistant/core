"""The tests for the Scene component."""
import io
import unittest

from homeassistant.components import light, scene
from homeassistant.setup import async_setup_component, setup_component
from homeassistant.util.yaml import loader as yaml_loader

from tests.common import get_test_home_assistant, mock_service
from tests.components.light import common as common_light
from tests.components.scene import common


class TestScene(unittest.TestCase):
    """Test the scene component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        test_light = getattr(self.hass.components, "test.light")
        test_light.init()

        assert setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {"platform": "test"}}
        )
        self.hass.block_till_done()

        self.light_1, self.light_2 = test_light.ENTITIES[0:2]

        common_light.turn_off(
            self.hass, [self.light_1.entity_id, self.light_2.entity_id]
        )

        self.hass.block_till_done()

        assert not self.light_1.is_on
        assert not self.light_2.is_on
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
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
        entity_state = {"state": "on", "brightness": 100}
        assert setup_component(
            self.hass,
            scene.DOMAIN,
            {
                "scene": [
                    {
                        "name": "test",
                        "entities": {
                            self.light_1.entity_id: entity_state,
                            self.light_2.entity_id: entity_state,
                        },
                    }
                ]
            },
        )
        self.hass.block_till_done()

        common.activate(self.hass, "scene.test")
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert 100 == self.light_1.last_call("turn_on")[1].get("brightness")
        assert 100 == self.light_2.last_call("turn_on")[1].get("brightness")

    def test_config_yaml_bool(self):
        """Test parsing of booleans in yaml config."""
        config = (
            "scene:\n"
            "  - name: test\n"
            "    entities:\n"
            f"      {self.light_1.entity_id}: on\n"
            f"      {self.light_2.entity_id}:\n"
            "        state: on\n"
            "        brightness: 100\n"
        )

        with io.StringIO(config) as file:
            doc = yaml_loader.yaml.safe_load(file)

        assert setup_component(self.hass, scene.DOMAIN, doc)
        common.activate(self.hass, "scene.test")
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert 100 == self.light_2.last_call("turn_on")[1].get("brightness")

    def test_activate_scene(self):
        """Test active scene."""
        assert setup_component(
            self.hass,
            scene.DOMAIN,
            {
                "scene": [
                    {
                        "name": "test",
                        "entities": {
                            self.light_1.entity_id: "on",
                            self.light_2.entity_id: {"state": "on", "brightness": 100},
                        },
                    }
                ]
            },
        )
        self.hass.block_till_done()

        common.activate(self.hass, "scene.test")
        self.hass.block_till_done()

        assert self.light_1.is_on
        assert self.light_2.is_on
        assert self.light_2.last_call("turn_on")[1].get("brightness") == 100

        turn_on_calls = mock_service(self.hass, "light", "turn_on")

        self.hass.services.call(
            scene.DOMAIN, "turn_on", {"transition": 42, "entity_id": "scene.test"}
        )
        self.hass.block_till_done()

        assert len(turn_on_calls) == 1
        assert turn_on_calls[0].domain == "light"
        assert turn_on_calls[0].service == "turn_on"
        assert turn_on_calls[0].data.get("transition") == 42


async def test_services_registered(hass):
    """Test we register services with empty config."""
    assert await async_setup_component(hass, "scene", {})
    assert hass.services.has_service("scene", "reload")
    assert hass.services.has_service("scene", "turn_on")
    assert hass.services.has_service("scene", "apply")
