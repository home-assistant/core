"""The tests for the Light component."""
# pylint: disable=protected-access
from io import StringIO
import os

import pytest
import voluptuous as vol

from homeassistant import core
from homeassistant.components import light
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    ENTITY_MATCH_ALL,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

import tests.async_mock as mock
from tests.common import async_mock_service


@pytest.fixture
def mock_storage(hass, hass_storage):
    """Clean up user light files at the end."""
    yield
    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)

    if os.path.isfile(user_light_file):
        os.remove(user_light_file)


async def test_methods(hass):
    """Test if methods call the services as expected."""
    # Test is_on
    hass.states.async_set("light.test", STATE_ON)
    assert light.is_on(hass, "light.test")

    hass.states.async_set("light.test", STATE_OFF)
    assert not light.is_on(hass, "light.test")

    # Test turn_on
    turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "entity_id_val",
            light.ATTR_TRANSITION: "transition_val",
            light.ATTR_BRIGHTNESS: "brightness_val",
            light.ATTR_RGB_COLOR: "rgb_color_val",
            light.ATTR_XY_COLOR: "xy_color_val",
            light.ATTR_PROFILE: "profile_val",
            light.ATTR_COLOR_NAME: "color_name_val",
            light.ATTR_WHITE_VALUE: "white_val",
        },
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    call = turn_on_calls[-1]

    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "entity_id_val"
    assert call.data.get(light.ATTR_TRANSITION) == "transition_val"
    assert call.data.get(light.ATTR_BRIGHTNESS) == "brightness_val"
    assert call.data.get(light.ATTR_RGB_COLOR) == "rgb_color_val"
    assert call.data.get(light.ATTR_XY_COLOR) == "xy_color_val"
    assert call.data.get(light.ATTR_PROFILE) == "profile_val"
    assert call.data.get(light.ATTR_COLOR_NAME) == "color_name_val"
    assert call.data.get(light.ATTR_WHITE_VALUE) == "white_val"

    # Test turn_off
    turn_off_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_OFF)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "entity_id_val",
            light.ATTR_TRANSITION: "transition_val",
        },
        blocking=True,
    )

    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data[ATTR_ENTITY_ID] == "entity_id_val"
    assert call.data[light.ATTR_TRANSITION] == "transition_val"

    # Test toggle
    toggle_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TOGGLE)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "entity_id_val", light.ATTR_TRANSITION: "transition_val"},
        blocking=True,
    )

    assert len(toggle_calls) == 1
    call = toggle_calls[-1]

    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TOGGLE
    assert call.data[ATTR_ENTITY_ID] == "entity_id_val"
    assert call.data[light.ATTR_TRANSITION] == "transition_val"


async def test_services(hass):
    """Test the provided services."""
    platform = getattr(hass.components, "test.light")

    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, ent2, ent3 = platform.ENTITIES

    # Test init
    assert light.is_on(hass, ent1.entity_id)
    assert not light.is_on(hass, ent2.entity_id)
    assert not light.is_on(hass, ent3.entity_id)

    # Test basic turn_on, turn_off, toggle services
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ent1.entity_id}, blocking=True
    )
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ent2.entity_id}, blocking=True
    )

    assert not light.is_on(hass, ent1.entity_id)
    assert light.is_on(hass, ent2.entity_id)

    # turn on all lights
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )

    assert light.is_on(hass, ent1.entity_id)
    assert light.is_on(hass, ent2.entity_id)
    assert light.is_on(hass, ent3.entity_id)

    # turn off all lights
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    assert not light.is_on(hass, ent1.entity_id)
    assert not light.is_on(hass, ent2.entity_id)
    assert not light.is_on(hass, ent3.entity_id)

    # turn off all lights by setting brightness to 0
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL, light.ATTR_BRIGHTNESS: 0},
        blocking=True,
    )

    assert not light.is_on(hass, ent1.entity_id)
    assert not light.is_on(hass, ent2.entity_id)
    assert not light.is_on(hass, ent3.entity_id)

    # toggle all lights
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )

    assert light.is_on(hass, ent1.entity_id)
    assert light.is_on(hass, ent2.entity_id)
    assert light.is_on(hass, ent3.entity_id)

    # toggle all lights
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )

    assert not light.is_on(hass, ent1.entity_id)
    assert not light.is_on(hass, ent2.entity_id)
    assert not light.is_on(hass, ent3.entity_id)

    # Ensure all attributes process correctly
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent1.entity_id,
            light.ATTR_TRANSITION: 10,
            light.ATTR_BRIGHTNESS: 20,
            light.ATTR_COLOR_NAME: "blue",
        },
        blocking=True,
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent2.entity_id,
            light.ATTR_RGB_COLOR: (255, 255, 255),
            light.ATTR_WHITE_VALUE: 255,
        },
        blocking=True,
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent3.entity_id,
            light.ATTR_XY_COLOR: (0.4, 0.6),
        },
        blocking=True,
    )

    _, data = ent1.last_call("turn_on")
    assert data == {
        light.ATTR_TRANSITION: 10,
        light.ATTR_BRIGHTNESS: 20,
        light.ATTR_HS_COLOR: (240, 100),
    }

    _, data = ent2.last_call("turn_on")
    assert data == {light.ATTR_HS_COLOR: (0, 0), light.ATTR_WHITE_VALUE: 255}

    _, data = ent3.last_call("turn_on")
    assert data == {light.ATTR_HS_COLOR: (71.059, 100)}

    # Ensure attributes are filtered when light is turned off
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent1.entity_id,
            light.ATTR_TRANSITION: 10,
            light.ATTR_BRIGHTNESS: 0,
            light.ATTR_COLOR_NAME: "blue",
        },
        blocking=True,
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent2.entity_id,
            light.ATTR_BRIGHTNESS: 0,
            light.ATTR_RGB_COLOR: (255, 255, 255),
            light.ATTR_WHITE_VALUE: 0,
        },
        blocking=True,
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent3.entity_id,
            light.ATTR_BRIGHTNESS: 0,
            light.ATTR_XY_COLOR: (0.4, 0.6),
        },
        blocking=True,
    )

    assert not light.is_on(hass, ent1.entity_id)
    assert not light.is_on(hass, ent2.entity_id)
    assert not light.is_on(hass, ent3.entity_id)

    _, data = ent1.last_call("turn_off")
    assert data == {light.ATTR_TRANSITION: 10}

    _, data = ent2.last_call("turn_off")
    assert data == {}

    _, data = ent3.last_call("turn_off")
    assert data == {}

    # One of the light profiles
    prof_name, prof_h, prof_s, prof_bri, prof_t = "relax", 35.932, 69.412, 144, 0

    # Test light profiles
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ent1.entity_id, light.ATTR_PROFILE: prof_name},
        blocking=True,
    )
    # Specify a profile and a brightness attribute to overwrite it
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent2.entity_id,
            light.ATTR_PROFILE: prof_name,
            light.ATTR_BRIGHTNESS: 100,
            light.ATTR_TRANSITION: 1,
        },
        blocking=True,
    )

    _, data = ent1.last_call("turn_on")
    assert data == {
        light.ATTR_BRIGHTNESS: prof_bri,
        light.ATTR_HS_COLOR: (prof_h, prof_s),
        light.ATTR_TRANSITION: prof_t,
    }

    _, data = ent2.last_call("turn_on")
    assert data == {
        light.ATTR_BRIGHTNESS: 100,
        light.ATTR_HS_COLOR: (prof_h, prof_s),
        light.ATTR_TRANSITION: 1,
    }

    # Test toggle with parameters
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TOGGLE,
        {
            ATTR_ENTITY_ID: ent3.entity_id,
            light.ATTR_PROFILE: prof_name,
            light.ATTR_BRIGHTNESS_PCT: 100,
        },
        blocking=True,
    )

    _, data = ent3.last_call("turn_on")
    assert data == {
        light.ATTR_BRIGHTNESS: 255,
        light.ATTR_HS_COLOR: (prof_h, prof_s),
        light.ATTR_TRANSITION: prof_t,
    }

    # Test bad data
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ent1.entity_id, light.ATTR_PROFILE: -1},
        blocking=True,
    )
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ent2.entity_id, light.ATTR_XY_COLOR: ["bla-di-bla", 5]},
            blocking=True,
        )
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ent3.entity_id, light.ATTR_RGB_COLOR: [255, None, 2]},
            blocking=True,
        )

    _, data = ent1.last_call("turn_on")
    assert data == {}

    _, data = ent2.last_call("turn_on")
    assert data == {}

    _, data = ent3.last_call("turn_on")
    assert data == {}

    # faulty attributes will not trigger a service call
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ent1.entity_id,
                light.ATTR_PROFILE: prof_name,
                light.ATTR_BRIGHTNESS: "bright",
            },
            blocking=True,
        )
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: ent1.entity_id,
                light.ATTR_RGB_COLOR: "yellowish",
            },
            blocking=True,
        )
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ent2.entity_id, light.ATTR_WHITE_VALUE: "high"},
            blocking=True,
        )

    _, data = ent1.last_call("turn_on")
    assert data == {}

    _, data = ent2.last_call("turn_on")
    assert data == {}


async def test_broken_light_profiles(hass, mock_storage):
    """Test light profiles."""
    platform = getattr(hass.components, "test.light")
    platform.init()

    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)

    # Setup a wrong light file
    with open(user_light_file, "w") as user_file:
        user_file.write("id,x,y,brightness,transition\n")
        user_file.write("I,WILL,NOT,WORK,EVER\n")

    assert not await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )


async def test_light_profiles(hass, mock_storage):
    """Test light profiles."""
    platform = getattr(hass.components, "test.light")
    platform.init()

    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)

    with open(user_light_file, "w") as user_file:
        user_file.write("id,x,y,brightness\n")
        user_file.write("test,.4,.6,100\n")
        user_file.write("test_off,0,0,0\n")

    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, _, _ = platform.ENTITIES

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ent1.entity_id,
            light.ATTR_PROFILE: "test",
        },
        blocking=True,
    )

    _, data = ent1.last_call("turn_on")
    assert light.is_on(hass, ent1.entity_id)
    assert data == {
        light.ATTR_HS_COLOR: (71.059, 100),
        light.ATTR_BRIGHTNESS: 100,
        light.ATTR_TRANSITION: 0,
    }

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ent1.entity_id, light.ATTR_PROFILE: "test_off"},
        blocking=True,
    )

    _, data = ent1.last_call("turn_off")
    assert not light.is_on(hass, ent1.entity_id)
    assert data == {light.ATTR_TRANSITION: 0}


async def test_light_profiles_with_transition(hass, mock_storage):
    """Test light profiles with transition."""
    platform = getattr(hass.components, "test.light")
    platform.init()

    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)

    with open(user_light_file, "w") as user_file:
        user_file.write("id,x,y,brightness,transition\n")
        user_file.write("test,.4,.6,100,2\n")
        user_file.write("test_off,0,0,0,0\n")

    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, _, _ = platform.ENTITIES

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ent1.entity_id, light.ATTR_PROFILE: "test"},
        blocking=True,
    )

    _, data = ent1.last_call("turn_on")
    assert light.is_on(hass, ent1.entity_id)
    assert data == {
        light.ATTR_HS_COLOR: (71.059, 100),
        light.ATTR_BRIGHTNESS: 100,
        light.ATTR_TRANSITION: 2,
    }

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ent1.entity_id, light.ATTR_PROFILE: "test_off"},
        blocking=True,
    )

    _, data = ent1.last_call("turn_off")
    assert not light.is_on(hass, ent1.entity_id)
    assert data == {light.ATTR_TRANSITION: 0}


async def test_default_profiles_group(hass, mock_storage):
    """Test default turn-on light profile for all lights."""
    platform = getattr(hass.components, "test.light")
    platform.init()

    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)
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

    profile_data = "id,x,y,brightness,transition\ngroup.all_lights.default,.4,.6,99,2\n"
    with mock.patch("os.path.isfile", side_effect=_mock_isfile), mock.patch(
        "builtins.open", side_effect=_mock_open
    ):
        assert await async_setup_component(
            hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )
        await hass.async_block_till_done()

    ent, _, _ = platform.ENTITIES
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ent.entity_id}, blocking=True
    )

    _, data = ent.last_call("turn_on")
    assert data == {
        light.ATTR_HS_COLOR: (71.059, 100),
        light.ATTR_BRIGHTNESS: 99,
        light.ATTR_TRANSITION: 2,
    }


async def test_default_profiles_light(hass, mock_storage):
    """Test default turn-on light profile for a specific light."""
    platform = getattr(hass.components, "test.light")
    platform.init()

    user_light_file = hass.config.path(light.LIGHT_PROFILES_FILE)
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
        "id,x,y,brightness,transition\n"
        + "group.all_lights.default,.3,.5,200,0\n"
        + "light.ceiling_2.default,.6,.6,100,3\n"
    )
    with mock.patch("os.path.isfile", side_effect=_mock_isfile), mock.patch(
        "builtins.open", side_effect=_mock_open
    ):
        assert await async_setup_component(
            hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )
        await hass.async_block_till_done()

    dev = next(filter(lambda x: x.entity_id == "light.ceiling_2", platform.ENTITIES))
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: dev.entity_id,
        },
        blocking=True,
    )

    _, data = dev.last_call("turn_on")
    assert data == {
        light.ATTR_HS_COLOR: (50.353, 100),
        light.ATTR_BRIGHTNESS: 100,
        light.ATTR_TRANSITION: 3,
    }


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
        blocking=True,
        context=core.Context(user_id=hass_admin_user.id),
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
            blocking=True,
            context=core.Context(user_id=hass_admin_user.id),
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
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 90, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_step_pct": 10},
        blocking=True,
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
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 1},
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 3, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 2},
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 5, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 50},
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 128, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 99},
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 252, data

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity.entity_id, "brightness_pct": 100},
        blocking=True,
    )

    _, data = entity.last_call("turn_on")
    assert data["brightness"] == 255, data


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomLight(light.Light):
        pass

    CustomLight()
    assert "Light is deprecated, modify CustomLight" in caplog.text
