"""The tests for the magichome light platform."""
import unittest
import unittest.mock as mock

import pytest

from homeassistant.components.magichome import scene as magichome

from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def pymagichome_mock():
    """Mock magichome."""
    with mock.patch(
        "homeassistant.components.magichome.scene.MagicHomeScene"
    ) as device:
        yield device


class TestMagichomeScene(unittest.TestCase):
    """Test for Magichome scene platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        dev_dict = [
            {
                "deviceId": "20a9039d-6f58-4423-bff8-cd0f118d6bad",
                "deviceName": "sceneddt",
                "deviceType": "scene",
                "zone": "",
                "brand": "",
                "model": "",
                "icon": None,
                "properties": None,
                "actions": None,
                "extensions": None,
            }
        ]
        self.scene = magichome.MagicHomeScene(self.hass, dev_dict)

    def test_activate(self):
        """Test turn_off."""
        self.scene.activate()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
