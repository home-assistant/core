"""Philips Hue lights platform tests."""
import asyncio
from collections import deque
import logging
from unittest.mock import Mock

import aiohue
from aiohue.lights import Lights
from aiohue.groups import Groups
import pytest

from homeassistant import config_entries
from homeassistant.components import hue
import homeassistant.components.light.hue as hue_light
from homeassistant.util import color

_LOGGER = logging.getLogger(__name__)

HUE_LIGHT_NS = 'homeassistant.components.light.hue.'
GROUP_RESPONSE = {
    "1": {
        "name": "Group 1",
        "lights": [
            "1",
            "2"
        ],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 254,
            "hue": 10000,
            "sat": 254,
            "effect": "none",
            "xy": [
                0.5,
                0.5
            ],
            "ct": 250,
            "alert": "select",
            "colormode": "ct"
        },
        "state": {
            "any_on": True,
            "all_on": False,
        }
    },
    "2": {
        "name": "Group 2",
        "lights": [
            "3",
            "4",
            "5"
        ],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 153,
            "hue": 4345,
            "sat": 254,
            "effect": "none",
            "xy": [
                0.5,
                0.5
            ],
            "ct": 250,
            "alert": "select",
            "colormode": "ct"
        },
        "state": {
            "any_on": True,
            "all_on": False,
        }
    }
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
        "reachable": True
    },
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
        "reachable": True
    },
    "type": "Extended color light",
    "name": "Hue Lamp 1",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "456",
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
        "reachable": True
    },
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
        "xy": [.5, .4],
        "ct": 420,
        "alert": "none",
        "effect": "none",
        "colormode": "hs",
        "reachable": True
    },
    "type": "Extended color light",
    "name": "Hue Lamp 2 new",
    "modelid": "LCT001",
    "swversion": "66009461",
    "manufacturername": "Philips",
    "uniqueid": "123",
}
LIGHT_RESPONSE = {
    "1": LIGHT_1_ON,
    "2": LIGHT_2_OFF,
}


@pytest.fixture
def mock_bridge(hass):
    """Mock a Hue bridge."""
    bridge = Mock(
        available=True,
        allow_unreachable=False,
        allow_groups=False,
        api=Mock(),
        spec=hue.HueBridge
    )
    bridge.mock_requests = []
    # We're using a deque so we can schedule multiple responses
    # and also means that `popleft()` will blow up if we get more updates
    # than expected.
    bridge.mock_light_responses = deque()
    bridge.mock_group_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs['method'] = method
        kwargs['path'] = path
        bridge.mock_requests.append(kwargs)

        if path == 'lights':
            return bridge.mock_light_responses.popleft()
        if path == 'groups':
            return bridge.mock_group_responses.popleft()
        return None

    bridge.api.config.apiversion = '9.9.9'
    bridge.api.lights = Lights({}, mock_request)
    bridge.api.groups = Groups({}, mock_request)

    return bridge


async def setup_bridge(hass, mock_bridge):
    """Load the Hue light platform with the provided bridge."""
    hass.config.components.add(hue.DOMAIN)
    hass.data[hue.DOMAIN] = {'mock-host': mock_bridge}
    config_entry = config_entries.ConfigEntry(1, hue.DOMAIN, 'Mock Title', {
        'host': 'mock-host'
    }, 'test')
    await hass.config_entries.async_forward_entry_setup(config_entry, 'light')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_not_load_groups_if_old_bridge(hass, mock_bridge):
    """Test that we don't try to load gorups if bridge runs old software."""
    mock_bridge.api.config.apiversion = '1.12.0'
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
    # 1 All Lights group, 2 lights
    assert len(hass.states.async_all()) == 3

    lamp_1 = hass.states.get('light.hue_lamp_1')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 144
    assert lamp_1.attributes['hs_color'] == (36.067, 69.804)

    lamp_2 = hass.states.get('light.hue_lamp_2')
    assert lamp_2 is not None
    assert lamp_2.state == 'off'


async def test_lights_color_mode(hass, mock_bridge):
    """Test that lights only report appropriate color mode."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)

    lamp_1 = hass.states.get('light.hue_lamp_1')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 144
    assert lamp_1.attributes['hs_color'] == (36.067, 69.804)
    assert 'color_temp' not in lamp_1.attributes

    new_light1_on = LIGHT_1_ON.copy()
    new_light1_on['state'] = new_light1_on['state'].copy()
    new_light1_on['state']['colormode'] = 'ct'
    mock_bridge.mock_light_responses.append({
        "1": new_light1_on,
    })
    mock_bridge.mock_group_responses.append({})

    # Calling a service will trigger the updates to run
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.hue_lamp_2'
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    lamp_1 = hass.states.get('light.hue_lamp_1')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 144
    assert lamp_1.attributes['color_temp'] == 467
    assert 'hs_color' not in lamp_1.attributes


async def test_groups(hass, mock_bridge):
    """Test the update_lights function with some lights."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    # 1 all lights group, 2 hue group lights
    assert len(hass.states.async_all()) == 3

    lamp_1 = hass.states.get('light.group_1')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 254
    assert lamp_1.attributes['color_temp'] == 250

    lamp_2 = hass.states.get('light.group_2')
    assert lamp_2 is not None
    assert lamp_2.state == 'on'


async def test_new_group_discovered(hass, mock_bridge):
    """Test if 2nd update has a new group."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    new_group_response = dict(GROUP_RESPONSE)
    new_group_response['3'] = {
        "name": "Group 3",
        "lights": [
            "3",
            "4",
            "5"
        ],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 153,
            "hue": 4345,
            "sat": 254,
            "effect": "none",
            "xy": [
                0.5,
                0.5
            ],
            "ct": 250,
            "alert": "select",
            "colormode": "ct"
        },
        "state": {
            "any_on": True,
            "all_on": False,
        }
    }

    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(new_group_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.group_1'
    }, blocking=True)
    # 2x group update, 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 5
    assert len(hass.states.async_all()) == 4

    new_group = hass.states.get('light.group_3')
    assert new_group is not None
    assert new_group.state == 'on'
    assert new_group.attributes['brightness'] == 153
    assert new_group.attributes['color_temp'] == 250


async def test_new_light_discovered(hass, mock_bridge):
    """Test if 2nd update has a new light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 3

    new_light_response = dict(LIGHT_RESPONSE)
    new_light_response['3'] = {
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
            "reachable": True
        },
        "type": "Extended color light",
        "name": "Hue Lamp 3",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "789",
    }

    mock_bridge.mock_light_responses.append(new_light_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.hue_lamp_1'
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3
    assert len(hass.states.async_all()) == 4

    light = hass.states.get('light.hue_lamp_3')
    assert light is not None
    assert light.state == 'off'


async def test_other_group_update(hass, mock_bridge):
    """Test changing one group that will impact the state of other light."""
    mock_bridge.allow_groups = True
    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(GROUP_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 2
    assert len(hass.states.async_all()) == 3

    group_2 = hass.states.get('light.group_2')
    assert group_2 is not None
    assert group_2.name == 'Group 2'
    assert group_2.state == 'on'
    assert group_2.attributes['brightness'] == 153
    assert group_2.attributes['color_temp'] == 250

    updated_group_response = dict(GROUP_RESPONSE)
    updated_group_response['2'] = {
        "name": "Group 2 new",
        "lights": [
            "3",
            "4",
            "5"
        ],
        "type": "LightGroup",
        "action": {
            "on": False,
            "bri": 0,
            "hue": 0,
            "sat": 0,
            "effect": "none",
            "xy": [
                0,
                0
            ],
            "ct": 0,
            "alert": "none",
            "colormode": "ct"
        },
        "state": {
            "any_on": False,
            "all_on": False,
        }
    }

    mock_bridge.mock_light_responses.append({})
    mock_bridge.mock_group_responses.append(updated_group_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.group_1'
    }, blocking=True)
    # 2x group update, 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 5
    assert len(hass.states.async_all()) == 3

    group_2 = hass.states.get('light.group_2')
    assert group_2 is not None
    assert group_2.name == 'Group 2 new'
    assert group_2.state == 'off'


async def test_other_light_update(hass, mock_bridge):
    """Test changing one light that will impact state of other light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)

    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 3

    lamp_2 = hass.states.get('light.hue_lamp_2')
    assert lamp_2 is not None
    assert lamp_2.name == 'Hue Lamp 2'
    assert lamp_2.state == 'off'

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response['2'] = {
        "state": {
            "on": True,
            "bri": 100,
            "hue": 13088,
            "sat": 210,
            "xy": [.5, .4],
            "ct": 420,
            "alert": "none",
            "effect": "none",
            "colormode": "hs",
            "reachable": True
        },
        "type": "Extended color light",
        "name": "Hue Lamp 2 new",
        "modelid": "LCT001",
        "swversion": "66009461",
        "manufacturername": "Philips",
        "uniqueid": "123",
    }

    mock_bridge.mock_light_responses.append(updated_light_response)

    # Calling a service will trigger the updates to run
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.hue_lamp_1'
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3
    assert len(hass.states.async_all()) == 3

    lamp_2 = hass.states.get('light.hue_lamp_2')
    assert lamp_2 is not None
    assert lamp_2.name == 'Hue Lamp 2 new'
    assert lamp_2.state == 'on'
    assert lamp_2.attributes['brightness'] == 100


async def test_update_timeout(hass, mock_bridge):
    """Test bridge marked as not available if timeout error during update."""
    mock_bridge.api.lights.update = Mock(side_effect=asyncio.TimeoutError)
    mock_bridge.api.groups.update = Mock(side_effect=asyncio.TimeoutError)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0
    assert mock_bridge.available is False


async def test_update_unauthorized(hass, mock_bridge):
    """Test bridge marked as not available if unauthorized during update."""
    mock_bridge.api.lights.update = Mock(side_effect=aiohue.Unauthorized)
    mock_bridge.api.groups.update = Mock(side_effect=aiohue.Unauthorized)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 0
    assert len(hass.states.async_all()) == 0
    assert mock_bridge.available is False


async def test_light_turn_on_service(hass, mock_bridge):
    """Test calling the turn on service on a light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    light = hass.states.get('light.hue_lamp_2')
    assert light is not None
    assert light.state == 'off'

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response['2'] = LIGHT_2_ON

    mock_bridge.mock_light_responses.append(updated_light_response)

    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.hue_lamp_2',
        'brightness': 100,
        'color_temp': 300,
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    assert mock_bridge.mock_requests[1]['json'] == {
        'bri': 100,
        'on': True,
        'ct': 300,
        'effect': 'none',
        'alert': 'none',
    }

    assert len(hass.states.async_all()) == 3

    light = hass.states.get('light.hue_lamp_2')
    assert light is not None
    assert light.state == 'on'


async def test_light_turn_off_service(hass, mock_bridge):
    """Test calling the turn on service on a light."""
    mock_bridge.mock_light_responses.append(LIGHT_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    light = hass.states.get('light.hue_lamp_1')
    assert light is not None
    assert light.state == 'on'

    updated_light_response = dict(LIGHT_RESPONSE)
    updated_light_response['1'] = LIGHT_1_OFF

    mock_bridge.mock_light_responses.append(updated_light_response)

    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.hue_lamp_1',
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_bridge.mock_requests) == 3

    assert mock_bridge.mock_requests[1]['json'] == {
        'on': False,
        'alert': 'none',
    }

    assert len(hass.states.async_all()) == 3

    light = hass.states.get('light.hue_lamp_1')
    assert light is not None
    assert light.state == 'off'


def test_available():
    """Test available property."""
    light = hue_light.HueLight(
        light=Mock(state={'reachable': False}),
        request_bridge_update=None,
        bridge=Mock(allow_unreachable=False),
        is_group=False,
    )

    assert light.available is False

    light = hue_light.HueLight(
        light=Mock(state={'reachable': False}),
        request_bridge_update=None,
        bridge=Mock(allow_unreachable=True),
        is_group=False,
    )

    assert light.available is True

    light = hue_light.HueLight(
        light=Mock(state={'reachable': False}),
        request_bridge_update=None,
        bridge=Mock(allow_unreachable=False),
        is_group=True,
    )

    assert light.available is True


def test_hs_color():
    """Test hs_color property."""
    light = hue_light.HueLight(
        light=Mock(state={
            'colormode': 'ct',
            'hue': 1234,
            'sat': 123,
        }),
        request_bridge_update=None,
        bridge=Mock(),
        is_group=False,
    )

    assert light.hs_color is None

    light = hue_light.HueLight(
        light=Mock(state={
            'colormode': 'hs',
            'hue': 1234,
            'sat': 123,
        }),
        request_bridge_update=None,
        bridge=Mock(),
        is_group=False,
    )

    assert light.hs_color is None

    light = hue_light.HueLight(
        light=Mock(state={
            'colormode': 'xy',
            'hue': 1234,
            'sat': 123,
            'xy': [0.4, 0.5]
        }),
        request_bridge_update=None,
        bridge=Mock(),
        is_group=False,
    )

    assert light.hs_color == color.color_xy_to_hs(0.4, 0.5)
