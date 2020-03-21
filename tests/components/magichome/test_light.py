"""The tests for the magichome device platform."""
import unittest
import unittest.mock as mock

import pytest

from homeassistant.components import light
from homeassistant.components.magichome import light as magichome
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def pymagichome_mock():
    """Mock magichome."""
    with mock.patch(
        "homeassistant.components.magichome.light.MagicHomeLight"
    ) as device:
        yield device


class TestMagicHomeSwitchSetup(unittest.TestCase):
    """Test the magichome light."""

    PLATFORM = magichome
    COMPONENT = light
    THING = "light"

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch("homeassistant.components.magichome.light.MagicHomeLight")
    def test_setup_adds_proper_devices(self, mock_light):
        """Test if setup adds devices."""
        good_config = {
            "magichome": {},
            "light": {
                "platform": "magichome",
                "dev_ids": [
                    {
                        "deviceId": "6001948C9E43",
                        "deviceName": "BulbName",
                        "deviceType": "light",
                        "zone": "",
                        "brand": "",
                        "model": "AK001-ZJ210",
                        "icon": "http://wifij01us.magichue.net/images/light.png",
                        "properties": [{"name": "status", "value": "False"}],
                        "actions": [
                            "Query",
                            "TurnOff",
                            "TurnOn",
                            "SetBrightness",
                            "AdjustUpBrightness",
                            "AdjustDownBrightness",
                        ],
                        "extensions": None,
                    }
                ],
            },
        }
        assert setup_component(self.hass, light.DOMAIN, good_config)


class TestMagichomeLight(unittest.TestCase):
    """Test for Magichome light platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        dev_dict = [
            {
                "deviceId": "6001948C9E43",
                "deviceName": "BulbName",
                "deviceType": "light",
                "zone": "",
                "brand": "",
                "model": "AK001-ZJ210",
                "icon": "http://wifij01us.magichue.net/images/light.png",
                "properties": [{"name": "status", "value": "False"}],
                "actions": [
                    "Query",
                    "TurnOff",
                    "TurnOn",
                    "SetBrightness",
                    "AdjustUpBrightness",
                    "AdjustDownBrightness",
                ],
                "extensions": None,
            }
        ]
        self.light = magichome.MagicHomeLight(self.hass, dev_dict)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_turn_on_with_no_brightness(self):
        """Test turn_on."""
        self.light.turn_on()

    def test_turn_on_with_brightness(self):
        """Test brightness."""
        self.light.turn_on(brightness=45)

    def test_turn_off(self):
        """Test turn_off."""
        self.light.turn_off()
