"""The tests for the Light component."""
# pylint: disable=protected-access
import unittest
import unittest.mock as mock
import os
from io import StringIO

import pytest

from homeassistant import core
from homeassistant.component import magichome as MagicHomeApi
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_OFF,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    SERVICE_TOGGLE,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.components import light
from homeassistant.helpers.intent import IntentHandleError

from tests.common import (
    async_mock_service,
    mock_service,
    get_test_home_assistant,
    mock_storage,
)
from tests.components.light import common


class TestLight(unittest.TestCase):
    """Test the light module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        if os.path.isfile(user_light_file):
            os.remove(user_light_file)

    def test_methods(self):
        """Test if methods call the services as expected."""
        # Test is_on
        self.hass.states.set("light.dc4f22e3c446", STATE_ON)
        assert light.is_on(self.hass, "light.dc4f22e3c446")

        self.hass.states.set("light.dc4f22e3c446", STATE_OFF)
        assert not light.is_on(self.hass, "light.dc4f22e3c446")

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_ON)
        assert light.is_on(self.hass)

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_OFF)
        assert not light.is_on(self.hass)

        # Test turn_on
        turn_on_calls = mock_service(self.hass, light.DOMAIN, SERVICE_TURN_ON)

        common.turn_on(
            self.hass,
            entity_id="entity_id_val",
            transition="transition_val",
            brightness="brightness_val",
            rgb_color="rgb_color_val",
            xy_color="xy_color_val",
            profile="profile_val",
            color_name="color_name_val",
            white_value="white_val",
        )

        self.hass.block_till_done()

        assert 1 == len(turn_on_calls)
        call = turn_on_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TURN_ON == call.service
        assert "entity_id_val" == call.data.get(ATTR_ENTITY_ID)
        assert "transition_val" == call.data.get(light.ATTR_TRANSITION)
        assert "brightness_val" == call.data.get(light.ATTR_BRIGHTNESS)
        assert "rgb_color_val" == call.data.get(light.ATTR_RGB_COLOR)
        assert "xy_color_val" == call.data.get(light.ATTR_XY_COLOR)
        assert "profile_val" == call.data.get(light.ATTR_PROFILE)
        assert "color_name_val" == call.data.get(light.ATTR_COLOR_NAME)
        assert "white_val" == call.data.get(light.ATTR_WHITE_VALUE)

        # Test turn_off
        turn_off_calls = mock_service(self.hass, light.DOMAIN, SERVICE_TURN_OFF)

        common.turn_off(
            self.hass, entity_id="entity_id_val", transition="transition_val"
        )

        self.hass.block_till_done()

        assert 1 == len(turn_off_calls)
        call = turn_off_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TURN_OFF == call.service
        assert "entity_id_val" == call.data[ATTR_ENTITY_ID]
        assert "transition_val" == call.data[light.ATTR_TRANSITION]

        # Test toggle
        toggle_calls = mock_service(self.hass, light.DOMAIN, SERVICE_TOGGLE)

        common.toggle(self.hass, entity_id="entity_id_val", transition="transition_val")

        self.hass.block_till_done()

        assert 1 == len(toggle_calls)
        call = toggle_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TOGGLE == call.service
        assert "entity_id_val" == call.data[ATTR_ENTITY_ID]
        assert "transition_val" == call.data[light.ATTR_TRANSITION]

