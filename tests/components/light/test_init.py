"""The tests for the Light component."""
# pylint: disable=protected-access
from io import StringIO
import os
import unittest

import pytest

from homeassistant import core
from homeassistant.components import light
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component, setup_component

import tests.async_mock as mock
from tests.common import get_test_home_assistant, mock_service, mock_storage
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
        self.hass.states.set("light.test", STATE_ON)
        assert light.is_on(self.hass, "light.test")

        self.hass.states.set("light.test", STATE_OFF)
        assert not light.is_on(self.hass, "light.test")

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

    def test_services(self):
        """Test the provided services."""
        platform = getattr(self.hass.components, "test.light")

        platform.init()
        assert setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )
        self.hass.block_till_done()

        ent1, ent2, ent3 = platform.ENTITIES

        # Test init
        assert light.is_on(self.hass, ent1.entity_id)
        assert not light.is_on(self.hass, ent2.entity_id)
        assert not light.is_on(self.hass, ent3.entity_id)

        # Test basic turn_on, turn_off, toggle services
        common.turn_off(self.hass, entity_id=ent1.entity_id)
        common.turn_on(self.hass, entity_id=ent2.entity_id)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, ent1.entity_id)
        assert light.is_on(self.hass, ent2.entity_id)

        # turn on all lights
        common.turn_on(self.hass)

        self.hass.block_till_done()

        assert light.is_on(self.hass, ent1.entity_id)
        assert light.is_on(self.hass, ent2.entity_id)
        assert light.is_on(self.hass, ent3.entity_id)

        # turn off all lights
        common.turn_off(self.hass)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, ent1.entity_id)
        assert not light.is_on(self.hass, ent2.entity_id)
        assert not light.is_on(self.hass, ent3.entity_id)

        # turn off all lights by setting brightness to 0
        common.turn_on(self.hass)

        self.hass.block_till_done()

        common.turn_on(self.hass, brightness=0)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, ent1.entity_id)
        assert not light.is_on(self.hass, ent2.entity_id)
        assert not light.is_on(self.hass, ent3.entity_id)

        # toggle all lights
        common.toggle(self.hass)

        self.hass.block_till_done()

        assert light.is_on(self.hass, ent1.entity_id)
        assert light.is_on(self.hass, ent2.entity_id)
        assert light.is_on(self.hass, ent3.entity_id)

        # toggle all lights
        common.toggle(self.hass)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, ent1.entity_id)
        assert not light.is_on(self.hass, ent2.entity_id)
        assert not light.is_on(self.hass, ent3.entity_id)

        # Ensure all attributes process correctly
        common.turn_on(
            self.hass, ent1.entity_id, transition=10, brightness=20, color_name="blue"
        )
        common.turn_on(
            self.hass, ent2.entity_id, rgb_color=(255, 255, 255), white_value=255
        )
        common.turn_on(self.hass, ent3.entity_id, xy_color=(0.4, 0.6))

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_on")
        assert {
            light.ATTR_TRANSITION: 10,
            light.ATTR_BRIGHTNESS: 20,
            light.ATTR_HS_COLOR: (240, 100),
        } == data

        _, data = ent2.last_call("turn_on")
        assert {light.ATTR_HS_COLOR: (0, 0), light.ATTR_WHITE_VALUE: 255} == data

        _, data = ent3.last_call("turn_on")
        assert {light.ATTR_HS_COLOR: (71.059, 100)} == data

        # Ensure attributes are filtered when light is turned off
        common.turn_on(
            self.hass, ent1.entity_id, transition=10, brightness=0, color_name="blue"
        )
        common.turn_on(
            self.hass,
            ent2.entity_id,
            brightness=0,
            rgb_color=(255, 255, 255),
            white_value=0,
        )
        common.turn_on(self.hass, ent3.entity_id, brightness=0, xy_color=(0.4, 0.6))

        self.hass.block_till_done()

        assert not light.is_on(self.hass, ent1.entity_id)
        assert not light.is_on(self.hass, ent2.entity_id)
        assert not light.is_on(self.hass, ent3.entity_id)

        _, data = ent1.last_call("turn_off")
        assert {light.ATTR_TRANSITION: 10} == data

        _, data = ent2.last_call("turn_off")
        assert {} == data

        _, data = ent3.last_call("turn_off")
        assert {} == data

        # One of the light profiles
        prof_name, prof_h, prof_s, prof_bri = "relax", 35.932, 69.412, 144

        # Test light profiles
        common.turn_on(self.hass, ent1.entity_id, profile=prof_name)
        # Specify a profile and a brightness attribute to overwrite it
        common.turn_on(self.hass, ent2.entity_id, profile=prof_name, brightness=100)

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_on")
        assert {
            light.ATTR_BRIGHTNESS: prof_bri,
            light.ATTR_HS_COLOR: (prof_h, prof_s),
        } == data

        _, data = ent2.last_call("turn_on")
        assert {
            light.ATTR_BRIGHTNESS: 100,
            light.ATTR_HS_COLOR: (prof_h, prof_s),
        } == data

        # Test toggle with parameters
        common.toggle(self.hass, ent3.entity_id, profile=prof_name, brightness_pct=100)
        self.hass.block_till_done()
        _, data = ent3.last_call("turn_on")
        assert {
            light.ATTR_BRIGHTNESS: 255,
            light.ATTR_HS_COLOR: (prof_h, prof_s),
        } == data

        # Test bad data
        common.turn_on(self.hass)
        common.turn_on(self.hass, ent1.entity_id, profile="nonexisting")
        common.turn_on(self.hass, ent2.entity_id, xy_color=["bla-di-bla", 5])
        common.turn_on(self.hass, ent3.entity_id, rgb_color=[255, None, 2])

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_on")
        assert {} == data

        _, data = ent2.last_call("turn_on")
        assert {} == data

        _, data = ent3.last_call("turn_on")
        assert {} == data

        # faulty attributes will not trigger a service call
        common.turn_on(
            self.hass, ent1.entity_id, profile=prof_name, brightness="bright"
        )
        common.turn_on(self.hass, ent1.entity_id, rgb_color="yellowish")
        common.turn_on(self.hass, ent2.entity_id, white_value="high")

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_on")
        assert {} == data

        _, data = ent2.last_call("turn_on")
        assert {} == data

    def test_broken_light_profiles(self):
        """Test light profiles."""
        platform = getattr(self.hass.components, "test.light")
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        # Setup a wrong light file
        with open(user_light_file, "w") as user_file:
            user_file.write("id,x,y,brightness\n")
            user_file.write("I,WILL,NOT,WORK\n")

        assert not setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )

    def test_light_profiles(self):
        """Test light profiles."""
        platform = getattr(self.hass.components, "test.light")
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        with open(user_light_file, "w") as user_file:
            user_file.write("id,x,y,brightness\n")
            user_file.write("test,.4,.6,100\n")
            user_file.write("test_off,0,0,0\n")

        assert setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )
        self.hass.block_till_done()

        ent1, _, _ = platform.ENTITIES

        common.turn_on(self.hass, ent1.entity_id, profile="test")

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_on")

        assert light.is_on(self.hass, ent1.entity_id)
        assert {light.ATTR_HS_COLOR: (71.059, 100), light.ATTR_BRIGHTNESS: 100} == data

        common.turn_on(self.hass, ent1.entity_id, profile="test_off")

        self.hass.block_till_done()

        _, data = ent1.last_call("turn_off")

        assert not light.is_on(self.hass, ent1.entity_id)
        assert {} == data

    def test_default_profiles_group(self):
        """Test default turn-on light profile for all lights."""
        platform = getattr(self.hass.components, "test.light")
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)
        real_isfile = os.path.isfile
        real_open = open

        def _mock_isfile(path):
            if path == user_light_file:
                return True
            return real_isfile(path)

        def _mock_open(path, *args, **kwargs):
            if path == user_light_file:
                return StringIO(profile_data)
            return real_open(path, *args, **kwargs)

        profile_data = "id,x,y,brightness\ngroup.all_lights.default,.4,.6,99\n"
        with mock.patch("os.path.isfile", side_effect=_mock_isfile), mock.patch(
            "builtins.open", side_effect=_mock_open
        ), mock_storage():
            assert setup_component(
                self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
            )
            self.hass.block_till_done()

        ent, _, _ = platform.ENTITIES
        common.turn_on(self.hass, ent.entity_id)
        self.hass.block_till_done()
        _, data = ent.last_call("turn_on")
        assert {light.ATTR_HS_COLOR: (71.059, 100), light.ATTR_BRIGHTNESS: 99} == data

    def test_default_profiles_light(self):
        """Test default turn-on light profile for a specific light."""
        platform = getattr(self.hass.components, "test.light")
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)
        real_isfile = os.path.isfile
        real_open = open

        def _mock_isfile(path):
            if path == user_light_file:
                return True
            return real_isfile(path)

        def _mock_open(path, *args, **kwargs):
            if path == user_light_file:
                return StringIO(profile_data)
            return real_open(path, *args, **kwargs)

        profile_data = (
            "id,x,y,brightness\n"
            + "group.all_lights.default,.3,.5,200\n"
            + "light.ceiling_2.default,.6,.6,100\n"
        )
        with mock.patch("os.path.isfile", side_effect=_mock_isfile), mock.patch(
            "builtins.open", side_effect=_mock_open
        ), mock_storage():
            assert setup_component(
                self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
            )
            self.hass.block_till_done()

        dev = next(
            filter(lambda x: x.entity_id == "light.ceiling_2", platform.ENTITIES)
        )
        common.turn_on(self.hass, dev.entity_id)
        self.hass.block_till_done()
        _, data = dev.last_call("turn_on")
        assert {light.ATTR_HS_COLOR: (50.353, 100), light.ATTR_BRIGHTNESS: 100} == data


async def test_light_context(hass, hass_admin_user):
    """Test that light context works."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(hass, "light", {"light": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling")
    assert state is not None

    await hass.services.async_call(
        "light",
        "toggle",
        {"entity_id": state.entity_id},
        True,
        core.Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("light.ceiling")
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id


async def test_light_turn_on_auth(hass, hass_admin_user):
    """Test that light context works."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(hass, "light", {"light": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("light.ceiling")
    assert state is not None

    hass_admin_user.mock_policy({})

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": state.entity_id},
            True,
            core.Context(user_id=hass_admin_user.id),
        )


async def test_light_brightness_step(hass):
    """Test that light context works."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    entity = platform.ENTITIES[0]
    entity.supported_features = light.SUPPORT_BRIGHTNESS
    entity.brightness = 100
    assert await async_setup_component(hass, "light", {"light": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["brightness"] == 100

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_step": -10},
        True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 90, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_step_pct": 10},
        True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 126, data


async def test_light_brightness_pct_conversion(hass):
    """Test that light brightness percent conversion."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    entity = platform.ENTITIES[0]
    entity.supported_features = light.SUPPORT_BRIGHTNESS
    entity.brightness = 100
    assert await async_setup_component(hass, "light", {"light": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["brightness"] == 100

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity.entity_id, "brightness_pct": 1}, True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 3, data

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity.entity_id, "brightness_pct": 2}, True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 5, data

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity.entity_id, "brightness_pct": 50}, True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 128, data

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity.entity_id, "brightness_pct": 99}, True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 252, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 100},
        True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 255, data


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomLight(light.Light):
        pass

    CustomLight()
    assert "Light is deprecated, modify CustomLight" in caplog.text
