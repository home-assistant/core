"""The tests for the MagicHome component."""
import json
import os
import unittest.mock as mock

import pytest

from homeassistant.components import magichome
from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_history(hass):
    """Mock history component loaded."""
    hass.config.components.add("history")


@pytest.fixture(autouse=True)
def magichome_cleanup(hass):
    """Clean up device tracker magichome file."""
    yield
    try:
        os.remove(hass.config.path(YAML_DEVICES))
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def pymagichome_mock():
    """Mock magichome."""
    with mock.patch(
        "homeassistant.components.magichome.light.MagicHomeLight"
    ) as device:
        yield device


async def test_setting_up_magichome(hass):
    """Test if we can set up the magichome and dump it to JSON."""
    assert await async_setup_component(
        hass,
        magichome.DOMAIN,
        {
            "magichome": {
                "username": "test@user.com",
                "password": "123456",
            }
        },
    )
    await hass.async_start()

    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:
        pytest.fail(
            "Unable to convert all magichome entities to JSON. "
            "Wrong data in state machine!"
        )


async def test_light(hass):
    """Test MagicHome Light."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = hass
        dev_dict = [
            {
                "deviceId": "6001948C9E43",
                "deviceName": "BulbName",
                "deviceType": "light",
                "zone": "",
                "brand": "",
                "model": "AK001-ZJ210",
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


async def test_scene(hass):
    """Test for Magichome scene platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = hass
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
