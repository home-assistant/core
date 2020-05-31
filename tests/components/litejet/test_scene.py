"""The tests for the litejet component."""
import logging
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.components import litejet

from tests.common import get_test_home_assistant
from tests.components.scene import common

_LOGGER = logging.getLogger(__name__)

ENTITY_SCENE = "scene.mock_scene_1"
ENTITY_SCENE_NUMBER = 1
ENTITY_OTHER_SCENE = "scene.mock_scene_2"
ENTITY_OTHER_SCENE_NUMBER = 2


class TestLiteJetScene(unittest.TestCase):
    """Test the litejet component."""

    @mock.patch("homeassistant.components.litejet.LiteJet")
    def setup_method(self, method, mock_pylitejet):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        def get_scene_name(number):
            return f"Mock Scene #{number}"

        self.mock_lj = mock_pylitejet.return_value
        self.mock_lj.loads.return_value = range(0)
        self.mock_lj.button_switches.return_value = range(0)
        self.mock_lj.all_switches.return_value = range(0)
        self.mock_lj.scenes.return_value = range(1, 3)
        self.mock_lj.get_scene_name.side_effect = get_scene_name

        assert setup.setup_component(
            self.hass,
            litejet.DOMAIN,
            {"litejet": {"port": "/dev/serial/by-id/mock-litejet"}},
        )
        self.hass.block_till_done()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def scene(self):
        """Get the current scene."""
        return self.hass.states.get(ENTITY_SCENE)

    def other_scene(self):
        """Get the other scene."""
        return self.hass.states.get(ENTITY_OTHER_SCENE)

    def test_activate(self):
        """Test activating the scene."""
        common.activate(self.hass, ENTITY_SCENE)
        self.hass.block_till_done()
        self.mock_lj.activate_scene.assert_called_once_with(ENTITY_SCENE_NUMBER)
