"""Philips Hue lights platform tests."""
import asyncio
import logging

import aiohue

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import light as hue_light
from homeassistant.util import color

from tests.async_mock import Mock

_LOGGER = logging.getLogger(__name__)

HUE_LIGHT_NS = "homeassistant.components.light.hue."
GROUP_RESPONSE = {
    "1": {
        "name": "Group 1",
        "lights": ["1", "2"],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 254,
            "hue": 10000,
            "sat": 254,
            "effect": "none",
            "xy": [0.5, 0.5],
            "ct": 250,
            "alert": "select",
            "colormode": "ct",
        },
        "state": {"any_on": True, "all_on": False},
    },
    "2": {
        "name": "Group 2",
        "lights": ["3", "4", "5"],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 153,
            "hue": 4345,
            "sat": 254,
            "effect": "none",
            "xy": [0.5, 0.5],
            "ct": 250,
            "alert": "select",
            "colormode": "ct",
        },
        "state": {"any_on": True, "all_on": False},
    },
}
LIGHT_1_CAPABILITIES = {
    "certified": True,
    "control": {
        "mindimlevel": 5000,
        "maxlumen": 600,
        "colorgamuttype": "A",
        "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
        "ct": {"min": 153, "max": 500},
    },
    "streaming": {"renderer": True, "proxy": False},
}
LIGHT_1_ON = {
    "state": {
        "on": True,
        "bri": 144,
        "hue": 13088,
        "sat": 212,
        "xy": [0.5128, 0.4147],
        "ct": 467,
        "alert": "none",
        "effect": "none",
        "colormode": "xy",
        "reachable": True,
    },
    "capabilities": LIGHT_1_CAPABILITIES,
    "type": "Extended color light",
    "name": "Hue Lamp 1",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "456",
}
LIGHT_1_OFF = {
    "state": {
        "on": False,
        "bri": 0,
        "hue": 0,
        "sat": 0,
        "xy": [0, 0],
        "ct": 0,
        "alert": "none",
        "effect": "none",
        "colormode": "xy",
        "reachable": True,
    },
    "capabilities": LIGHT_1_CAPABILITIES,
    "type": "Extended color light",
    "name": "Hue Lamp 1",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "456",
}
LIGHT_2_CAPABILITIES = {
    "certified": True,
    "control": {
        "mindimlevel": 5000,
        "maxlumen": 600,
        "colorgamuttype": "A",
        "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
    },
    "streaming": {"renderer": True, "proxy": False},
}
LIGHT_2_OFF = {
    "state": {
        "on": False,
        "bri": 0,
        "hue": 0,
        "sat": 0,
        "xy": [0, 0],
        "ct": 0,
        "alert": "none",
        "effect": "none",
        "colormode": "hs",
        "reachable": True,
    },
    "capabilities": LIGHT_2_CAPABILITIES,
    "type": "Extended color light",
    "name": "Hue Lamp 2",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "123",
}
LIGHT_2_ON = {
    "state": {
        "on": True,
        "bri": 100,
        "hue": 13088,
        "sat": 210,
        "xy": [0.5, 0.4],
        "ct": 420,
        "alert": "none",
        "effect": "none",
        "colormode": "hs",
        "reachable": True,
    },
    "capabilities": LIGHT_2_CAPABILITIES,
    "type": "Extended color light",
    "name": "Hue Lamp 2 new",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "123",
}
LIGHT_RESPONSE = {"1": LIGHT_1_ON, "2": LIGHT_2_OFF}
LIGHT_RAW = {
    "capabilities": {
        "control": {
            "colorgamuttype": "A",
            "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
        }
    },
    "swversion": "66009461",
}
LIGHT_GAMUT = color.GamutType(
    color.XYPoint(0.704, 0.296),
    color.XYPoint(0.2151, 0.7106),
    color.XYPoint(0.138, 0.08),
)
LIGHT_GAMUT_TYPE = "A"


async def setup_bridge(hass, mock_bridge):
    """Load the Hue light platform with the provided bridge."""
    hass.config.components.add(hue.DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        hue.DOMAIN,
        "Mock Title",
        {"host": "mock-host"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
    )
    mock_bridge.config_entry = config_entry
    hass.data[hue.DOMAIN] = {config_entry.entry_id: mock_bridge}
    await hass.config_entries.async_forward_entry_setup(config_entry, "light")
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_not_load_groups_if_old_bridge(hass, mock_bridge):
    """Test that we don't try to load gorups if bridge runs old software."""
    mock_bridge.api.config.apiversion = "1.12.0"
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 0


async def test_no_lights_or_groups(hass, mock_bridge):
    """Test the update_lights function when no lights are found."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append({})
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 0


async def test_lights(hass, mock_bridge):
    """Test the update_lights function with some lights."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    # 2 lights
    assert len(hass.states.async_all()) == 2

    lamp_1 = hass.states.get("light.hue_lamp_1")
    assert lamp_1 is not None
    assert lamp_1.state == "on"
    assert lamp_1.attributes["brightness"] == 145
    assert lamp_1.attributes["hs_color"] == (36.067, 69.804)

    lamp_2 = hass.states.get("light.hue_lamp_2")
    assert lamp_2 is not None
    assert lamp_2.state == "off"


async def test_lights_color_mode(hass, mock_bridge):
    """Test that lights only report appropriate color mode."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)

    lamp_1 = hass.states.get("light.hue_lamp_1")
    assert lamp_1 is not None
    assert lamp_1.state == "on"
    assert lamp_1.attributes["brightness"] == 145
    assert lamp_1.attributes["hs_color"] == (36.067, 69.804)
    assert "color_temp" not in lamp_1.attributes

    new_light1_on = LIGHT_1_ON.copy()
    new_light1_on["state"] = new_light1_on["state"].copy()
    new_light1_on["state"]["colormode"] = "ct"
    mock_bridge.mock_light_responses.append({"1": new_light1_on})
    mock_bridge.mock_group_responses.append({})

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.hue_lamp_2"}, blocking=True
    )
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    lamp_1 = hass.states.get("light.hue_lamp_1")
    assert lamp_1 is not None
    assert lamp_1.state == "on"
    assert lamp_1.attributes["brightness"] == 145
    assert lamp_1.attributes["color_temp"] == 467
    assert "hs_color" not in lamp_1.attributes


async def test_groups(hass, mock_bridge):
    """Test the update_lights function with some lights."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    # 2 hue group lights
    assert len(hass.states.async_all()) == 2

    lamp_1 = hass.states.get("light.group_1")
    assert lamp_1 is not None
    assert lamp_1.state == "on"
    assert lamp_1.attributes["brightness"] == 255
    assert lamp_1.attributes["color_temp"] == 250

    lamp_2 = hass.states.get("light.group_2")
    assert lamp_2 is not None
    assert lamp_2.state == "on"


async def test_new_group_discovered(hass, mock_bridge):
    """Test if 2nd update has a new group."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 2

    new_group_response = dict(GROUP_RESPONSE)
    new_group_response["3"] = {
        "name": "Group 3",
        "lights": ["3", "4", "5"],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 153,
            "hue": 4345,
            "sat": 254,
            "effect": "none",
            "xy": [0.5, 0.5],
            "ct": 250,
            "alert": "select",
            "colormode": "ct",
        },
        "state": {"any_on": True, "all_on": False},
    }

    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(new_group_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.group_1"}, blocking=True
    )
    # 2x group update, 1x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 4
    assert len(hass.states.async_all()) == 3

    new_group = hass.states.get("light.group_3")
    assert new_group is not None
    assert new_group.state == "on"
    assert new_group.attributes["brightness"] == 154
    assert new_group.attributes["color_temp"] == 250


async def test_new_light_discovered(hass, mock_bridge):
    """Test if 2nd update has a new light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 2

    new_light_response = dict(LIGHT_RESPONSE)
    new_light_response["3"] = {
        "state": {
            "on": False,
            "bri": 0,
            "hue": 0,
            "sat": 0,
            "xy": [0, 0],
            "ct": 0,
            "alert": "none",
            "effect": "none",
            "colormode": "hs",
            "reachable": True,
        },
        "capabilities": LIGHT_1_CAPABILITIES,
        "type": "Extended color light",
        "name": "Hue Lamp 3",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "789",
    }

    mock_bridge.mock_light_responses.append(new_light_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.hue_lamp_1"}, blocking=True
    )
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3
    assert len(hass.states.async_all()) == 3

    light = hass.states.get("light.hue_lamp_3")
    assert light is not None
    assert light.state == "off"


async def test_group_removed(hass, mock_bridge):
    """Test if 2nd update has removed group."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 2

    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append({"1": GROUP_RESPONSE["1"]})

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.group_1"}, blocking=True
    )

    # 2x group update, 1x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 4
    assert len(hass.states.async_all()) == 1

    group = hass.states.get("light.group_1")
    assert group is not None

    removed_group = hass.states.get("light.group_2")
    assert removed_group is None


async def test_light_removed(hass, mock_bridge):
    """Test if 2nd update has removed light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 2

    mock_bridge.mock_light_responses.clear()
    mock_bridge.mock_light_responses.append({"1": LIGHT_RESPONSE.get("1")})

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.hue_lamp_1"}, blocking=True
    )

    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3
    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.hue_lamp_1")
    assert light is not None

    removed_light = hass.states.get("light.hue_lamp_2")
    assert removed_light is None


async def test_other_group_update(hass, mock_bridge):
    """Test changing one group that will impact the state of other light."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 2

    group_2 = hass.states.get("light.group_2")
    assert group_2 is not None
    assert group_2.name == "Group 2"
    assert group_2.state == "on"
    assert group_2.attributes["brightness"] == 154
    assert group_2.attributes["color_temp"] == 250

    updated_group_response = dict(GROUP_RESPONSE)
    updated_group_response["2"] = {
        "name": "Group 2 new",
        "lights": ["3", "4", "5"],
        "type": "LightGroup",
        "action": {
            "on": False,
            "bri": 0,
            "hue": 0,
            "sat": 0,
            "effect": "none",
            "xy": [0, 0],
            "ct": 0,
            "alert": "none",
            "colormode": "ct",
        },
        "state": {"any_on": False, "all_on": False},
    }

    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(updated_group_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.group_1"}, blocking=True
    )
    # 2x group update, 1x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 4
    assert len(hass.states.async_all()) == 2

    group_2 = hass.states.get("light.group_2")
    assert group_2 is not None
    assert group_2.name == "Group 2 new"
    assert group_2.state == "off"


async def test_other_light_update(hass, mock_bridge):
    """Test changing one light that will impact state of other light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 2

    lamp_2 = hass.states.get("light.hue_lamp_2")
    assert lamp_2 is not None
    assert lamp_2.name == "Hue Lamp 2"
    assert lamp_2.state == "off"

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response["2"] = {
        "state": {
            "on": True,
            "bri": 100,
            "hue": 13088,
            "sat": 210,
            "xy": [0.5, 0.4],
            "ct": 420,
            "alert": "none",
            "effect": "none",
            "colormode": "hs",
            "reachable": True,
        },
        "capabilities": LIGHT_2_CAPABILITIES,
        "type": "Extended color light",
        "name": "Hue Lamp 2 new",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "123",
    }

    mock_bridge.mock_light_responses.append(updated_light_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.hue_lamp_1"}, blocking=True
    )
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3
    assert len(hass.states.async_all()) == 2

    lamp_2 = hass.states.get("light.hue_lamp_2")
    assert lamp_2 is not None
    assert lamp_2.name == "Hue Lamp 2 new"
    assert lamp_2.state == "on"
    assert lamp_2.attributes["brightness"] == 100


async def test_update_timeout(hass, mock_bridge):
    """Test bridge marked as not available if timeout error during update."""
    mock_bridge.api.lights.update = Mock(side_effect=asyncio.TimeoutError)
    mock_bridge.api.groups.update = Mock(side_effect=asyncio.TimeoutError)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0


async def test_update_unauthorized(hass, mock_bridge):
    """Test bridge marked as not authorized if unauthorized during update."""
    mock_bridge.api.lights.update = Mock(side_effect=aiohue.Unauthorized)
    mock_bridge.api.groups.update = Mock(side_effect=aiohue.Unauthorized)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0
    assert len(mock_bridge.handle_unauthorized_error.mock_calls) == 1


async def test_light_turn_on_service(hass, mock_bridge):
    """Test calling the turn on service on a light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    light = hass.states.get("light.hue_lamp_2")
    assert light is not None
    assert light.state == "off"

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response["2"] = LIGHT_2_ON

    mock_bridge.mock_light_responses.append(updated_light_response)

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_lamp_2", "brightness": 100, "color_temp": 300},
        blocking=True,
    )
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    assert mock_bridge.mock_requests[1]["json"] == {
        "bri": 100,
        "on": True,
        "ct": 300,
        "alert": "none",
    }

    assert len(hass.states.async_all()) == 2

    light = hass.states.get("light.hue_lamp_2")
    assert light is not None
    assert light.state == "on"

    # test hue gamut in turn_on service
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hue_lamp_2", "rgb_color": [0, 0, 255]},
        blocking=True,
    )

    assert len(mock_bridge.mock_requests) == 5

    assert mock_bridge.mock_requests[3]["json"] == {
        "on": True,
        "xy": (0.138, 0.08),
        "alert": "none",
    }


async def test_light_turn_off_service(hass, mock_bridge):
    """Test calling the turn on service on a light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    light = hass.states.get("light.hue_lamp_1")
    assert light is not None
    assert light.state == "on"

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response["1"] = LIGHT_1_OFF

    mock_bridge.mock_light_responses.append(updated_light_response)

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.hue_lamp_1"}, blocking=True
    )
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    assert mock_bridge.mock_requests[1]["json"] == {"on": False, "alert": "none"}

    assert len(hass.states.async_all()) == 2

    light = hass.states.get("light.hue_lamp_1")
    assert light is not None
    assert light.state == "off"


def test_available():
    """Test available property."""
    light = hue_light.HueLight(
        light=Mock(
            state={"reachable": False},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(allow_unreachable=False),
        is_group=False,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.available is False

    light = hue_light.HueLight(
        light=Mock(
            state={"reachable": False},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(allow_unreachable=True),
        is_group=False,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.available is True

    light = hue_light.HueLight(
        light=Mock(
            state={"reachable": False},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(allow_unreachable=False),
        is_group=True,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.available is True


def test_hs_color():
    """Test hs_color property."""
    light = hue_light.HueLight(
        light=Mock(
            state={"colormode": "ct", "hue": 1234, "sat": 123},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(),
        is_group=False,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.hs_color is None

    light = hue_light.HueLight(
        light=Mock(
            state={"colormode": "hs", "hue": 1234, "sat": 123},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(),
        is_group=False,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.hs_color is None

    light = hue_light.HueLight(
        light=Mock(
            state={"colormode": "xy", "hue": 1234, "sat": 123, "xy": [0.4, 0.5]},
            raw=LIGHT_RAW,
            colorgamuttype=LIGHT_GAMUT_TYPE,
            colorgamut=LIGHT_GAMUT,
        ),
        coordinator=Mock(last_update_success=True),
        bridge=Mock(),
        is_group=False,
        supported_features=hue_light.SUPPORT_HUE_EXTENDED,
    )

    assert light.hs_color == color.color_xy_to_hs(0.4, 0.5, LIGHT_GAMUT)


async def test_group_features(hass, mock_bridge):
    """Test group features."""

    color_temp_type = "Color temperature light"
    extended_color_type = "Extended color light"

    group_response = {
        "1": {
            "name": "Group 1",
            "lights": ["1", "2"],
            "type": "Room",
            "action": {
                "on": True,
                "bri": 254,
                "hue": 10000,
                "sat": 254,
                "effect": "none",
                "xy": [0.5, 0.5],
                "ct": 250,
                "alert": "select",
                "colormode": "ct",
            },
            "state": {"any_on": True, "all_on": False},
        },
        "2": {
            "name": "Group 2",
            "lights": ["3", "4"],
            "type": "Room",
            "action": {
                "on": True,
                "bri": 153,
                "hue": 4345,
                "sat": 254,
                "effect": "none",
                "xy": [0.5, 0.5],
                "ct": 250,
                "alert": "select",
                "colormode": "ct",
            },
            "state": {"any_on": True, "all_on": False},
        },
        "3": {
            "name": "Group 3",
            "lights": ["1", "3"],
            "type": "Room",
            "action": {
                "on": True,
                "bri": 153,
                "hue": 4345,
                "sat": 254,
                "effect": "none",
                "xy": [0.5, 0.5],
                "ct": 250,
                "alert": "select",
                "colormode": "ct",
            },
            "state": {"any_on": True, "all_on": False},
        },
    }

    light_1 = {
        "state": {
            "on": True,
            "bri": 144,
            "ct": 467,
            "alert": "none",
            "effect": "none",
            "reachable": True,
        },
        "capabilities": {
            "control": {
                "colorgamuttype": "A",
                "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
            }
        },
        "type": color_temp_type,
        "name": "Hue Lamp 1",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "456",
    }
    light_2 = {
        "state": {
            "on": False,
            "bri": 0,
            "ct": 0,
            "alert": "none",
            "effect": "none",
            "colormode": "xy",
            "reachable": True,
        },
        "capabilities": {
            "control": {
                "colorgamuttype": "A",
                "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
            }
        },
        "type": color_temp_type,
        "name": "Hue Lamp 2",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "4567",
    }
    light_3 = {
        "state": {
            "on": False,
            "bri": 0,
            "hue": 0,
            "sat": 0,
            "xy": [0, 0],
            "ct": 0,
            "alert": "none",
            "effect": "none",
            "colormode": "hs",
            "reachable": True,
        },
        "capabilities": {
            "control": {
                "colorgamuttype": "A",
                "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
            }
        },
        "type": extended_color_type,
        "name": "Hue Lamp 3",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "123",
    }
    light_4 = {
        "state": {
            "on": True,
            "bri": 100,
            "hue": 13088,
            "sat": 210,
            "xy": [0.5, 0.4],
            "ct": 420,
            "alert": "none",
            "effect": "none",
            "colormode": "hs",
            "reachable": True,
        },
        "capabilities": {
            "control": {
                "colorgamuttype": "A",
                "colorgamut": [[0.704, 0.296], [0.2151, 0.7106], [0.138, 0.08]],
            }
        },
        "type": extended_color_type,
        "name": "Hue Lamp 4",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "1234",
    }
    light_response = {
        "1": light_1,
        "2": light_2,
        "3": light_3,
        "4": light_4,
    }

    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append(light_response)
    mock_bridge.mock_group_responses.append(group_response)
    await setup_bridge(hass, mock_bridge)

    color_temp_feature = hue_light.SUPPORT_HUE["Color temperature light"]
    extended_color_feature = hue_light.SUPPORT_HUE["Extended color light"]

    group_1 = hass.states.get("light.group_1")
    assert group_1.attributes["supported_features"] == color_temp_feature

    group_2 = hass.states.get("light.group_2")
    assert group_2.attributes["supported_features"] == extended_color_feature

    group_3 = hass.states.get("light.group_3")
    assert group_3.attributes["supported_features"] == extended_color_feature
