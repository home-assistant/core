"""Test Google Smart Home."""
from unittest.mock import patch, Mock
import pytest

from homeassistant.core import State, EVENT_CALL_SERVICE
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
from homeassistant.setup import async_setup_component
from homeassistant.components import camera
from homeassistant.components.climate.const import (
    ATTR_MIN_TEMP, ATTR_MAX_TEMP, STATE_HEAT, SUPPORT_OPERATION_MODE
)
from homeassistant.components.google_assistant import (
    const, trait, helpers, smart_home as sh,
    EVENT_COMMAND_RECEIVED, EVENT_QUERY_RECEIVED, EVENT_SYNC_RECEIVED)
from homeassistant.components.demo.light import DemoLight

from homeassistant.helpers import device_registry
from tests.common import (mock_device_registry, mock_registry,
                          mock_area_registry, mock_coro)

BASIC_CONFIG = helpers.Config(
    should_expose=lambda state: True,
    allow_unlock=False
)
REQ_ID = 'ff36a3cc-ec34-11e6-b1a0-64510650abcf'


@pytest.fixture
def registries(hass):
    """Registry mock setup."""
    from types import SimpleNamespace
    ret = SimpleNamespace()
    ret.entity = mock_registry(hass)
    ret.device = mock_device_registry(hass)
    ret.area = mock_area_registry(hass)
    return ret


async def test_sync_message(hass):
    """Test a sync message."""
    light = DemoLight(
        None, 'Demo Light',
        state=False,
        hs_color=(180, 75),
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    await light.async_update_ha_state()

    # This should not show up in the sync request
    hass.states.async_set('sensor.no_match', 'something')

    # Excluded via config
    hass.states.async_set('light.not_expose', 'on')

    config = helpers.Config(
        should_expose=lambda state: state.entity_id != 'light.not_expose',
        allow_unlock=False,
        entity_config={
            'light.demo_light': {
                const.CONF_ROOM_HINT: 'Living Room',
                const.CONF_ALIASES: ['Hello', 'World']
            }
        }
    )

    events = []
    hass.bus.async_listen(EVENT_SYNC_RECEIVED, events.append)

    result = await sh.async_handle_message(
        hass, config, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.SYNC"
            }]
        })

    assert result == {
        'requestId': REQ_ID,
        'payload': {
            'agentUserId': 'test-agent',
            'devices': [{
                'id': 'light.demo_light',
                'name': {
                    'name': 'Demo Light',
                    'nicknames': [
                        'Hello',
                        'World',
                    ]
                },
                'traits': [
                    trait.TRAIT_BRIGHTNESS,
                    trait.TRAIT_ONOFF,
                    trait.TRAIT_COLOR_SPECTRUM,
                    trait.TRAIT_COLOR_TEMP,
                ],
                'type': sh.TYPE_LIGHT,
                'willReportState': False,
                'attributes': {
                    'colorModel': 'rgb',
                    'temperatureMinK': 2000,
                    'temperatureMaxK': 6535,
                },
                'roomHint': 'Living Room'
            }]
        }
    }
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_SYNC_RECEIVED
    assert events[0].data == {
        'request_id': REQ_ID,
    }


# pylint: disable=redefined-outer-name
async def test_sync_in_area(hass, registries):
    """Test a sync message where room hint comes from area."""
    area = registries.area.async_create("Living Room")

    device = registries.device.async_get_or_create(
        config_entry_id='1234',
        connections={
            (device_registry.CONNECTION_NETWORK_MAC, '12:34:56:AB:CD:EF')
        })
    registries.device.async_update_device(device.id, area_id=area.id)

    entity = registries.entity.async_get_or_create(
        'light', 'test', '1235',
        suggested_object_id='demo_light',
        device_id=device.id)

    light = DemoLight(
        None, 'Demo Light',
        state=False,
        hs_color=(180, 75),
    )
    light.hass = hass
    light.entity_id = entity.entity_id
    await light.async_update_ha_state()

    config = helpers.Config(
        should_expose=lambda _: True,
        allow_unlock=False,
        entity_config={}
    )

    events = []
    hass.bus.async_listen(EVENT_SYNC_RECEIVED, events.append)

    result = await sh.async_handle_message(
        hass, config, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.SYNC"
            }]
        })

    assert result == {
        'requestId': REQ_ID,
        'payload': {
            'agentUserId': 'test-agent',
            'devices': [{
                'id': 'light.demo_light',
                'name': {
                    'name': 'Demo Light'
                },
                'traits': [
                    trait.TRAIT_BRIGHTNESS,
                    trait.TRAIT_ONOFF,
                    trait.TRAIT_COLOR_SPECTRUM,
                    trait.TRAIT_COLOR_TEMP,
                ],
                'type': sh.TYPE_LIGHT,
                'willReportState': False,
                'attributes': {
                    'colorModel': 'rgb',
                    'temperatureMinK': 2000,
                    'temperatureMaxK': 6535,
                },
                'roomHint': 'Living Room'
            }]
        }
    }
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == EVENT_SYNC_RECEIVED
    assert events[0].data == {
        'request_id': REQ_ID,
    }


async def test_query_message(hass):
    """Test a sync message."""
    light = DemoLight(
        None, 'Demo Light',
        state=False,
        hs_color=(180, 75),
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    await light.async_update_ha_state()

    light2 = DemoLight(
        None, 'Another Light',
        state=True,
        hs_color=(180, 75),
        ct=400,
        brightness=78,
    )
    light2.hass = hass
    light2.entity_id = 'light.another_light'
    await light2.async_update_ha_state()

    events = []
    hass.bus.async_listen(EVENT_QUERY_RECEIVED, events.append)

    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.QUERY",
                "payload": {
                    "devices": [{
                        "id": "light.demo_light",
                    }, {
                        "id": "light.another_light",
                    }, {
                        "id": "light.non_existing",
                    }]
                }
            }]
        })

    assert result == {
        'requestId': REQ_ID,
        'payload': {
            'devices': {
                'light.non_existing': {
                    'online': False,
                },
                'light.demo_light': {
                    'on': False,
                    'online': True,
                },
                'light.another_light': {
                    'on': True,
                    'online': True,
                    'brightness': 30,
                    'color': {
                        'spectrumRGB': 4194303,
                        'temperature': 2500,
                    }
                },
            }
        }
    }

    assert len(events) == 3
    assert events[0].event_type == EVENT_QUERY_RECEIVED
    assert events[0].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.demo_light'
    }
    assert events[1].event_type == EVENT_QUERY_RECEIVED
    assert events[1].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.another_light'
    }
    assert events[2].event_type == EVENT_QUERY_RECEIVED
    assert events[2].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.non_existing'
    }


async def test_execute(hass):
    """Test an execute command."""
    await async_setup_component(hass, 'light', {
        'light': {'platform': 'demo'}
    })

    await hass.services.async_call(
        'light', 'turn_off', {'entity_id': 'light.ceiling_lights'},
        blocking=True)

    events = []
    hass.bus.async_listen(EVENT_COMMAND_RECEIVED, events.append)

    service_events = []
    hass.bus.async_listen(EVENT_CALL_SERVICE, service_events.append)

    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, None,
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.EXECUTE",
                "payload": {
                    "commands": [{
                        "devices": [
                            {"id": "light.non_existing"},
                            {"id": "light.ceiling_lights"},
                        ],
                        "execution": [{
                            "command": "action.devices.commands.OnOff",
                            "params": {
                                "on": True
                            }
                        }, {
                            "command":
                                "action.devices.commands.BrightnessAbsolute",
                            "params": {
                                "brightness": 20
                            }
                        }]
                    }]
                }
            }]
        })

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [{
                "ids": ['light.non_existing'],
                "status": "ERROR",
                "errorCode": "deviceOffline"
            }, {
                "ids": ['light.ceiling_lights'],
                "status": "SUCCESS",
                "states": {
                    "on": True,
                    "online": True,
                    'brightness': 20,
                    'color': {
                        'spectrumRGB': 16773155,
                        'temperature': 2631,
                    },
                }
            }]
        }
    }

    assert len(events) == 4
    assert events[0].event_type == EVENT_COMMAND_RECEIVED
    assert events[0].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.non_existing',
        'execution': {
            'command': 'action.devices.commands.OnOff',
            'params': {
                'on': True
            }
        }
    }
    assert events[1].event_type == EVENT_COMMAND_RECEIVED
    assert events[1].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.non_existing',
        'execution': {
            'command': 'action.devices.commands.BrightnessAbsolute',
            'params': {
                'brightness': 20
            }
        }
    }
    assert events[2].event_type == EVENT_COMMAND_RECEIVED
    assert events[2].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.ceiling_lights',
        'execution': {
            'command': 'action.devices.commands.OnOff',
            'params': {
                'on': True
            }
        }
    }
    assert events[3].event_type == EVENT_COMMAND_RECEIVED
    assert events[3].data == {
        'request_id': REQ_ID,
        'entity_id': 'light.ceiling_lights',
        'execution': {
            'command': 'action.devices.commands.BrightnessAbsolute',
            'params': {
                'brightness': 20
            }
        }
    }

    assert len(service_events) == 2
    assert service_events[0].data == {
        'domain': 'light',
        'service': 'turn_on',
        'service_data': {'entity_id': 'light.ceiling_lights'}
    }
    assert service_events[0].context == events[2].context
    assert service_events[1].data == {
        'domain': 'light',
        'service': 'turn_on',
        'service_data': {
            'brightness_pct': 20,
            'entity_id': 'light.ceiling_lights'
        }
    }
    assert service_events[1].context == events[2].context
    assert service_events[1].context == events[3].context


async def test_raising_error_trait(hass):
    """Test raising an error while executing a trait command."""
    hass.states.async_set('climate.bla', STATE_HEAT, {
        ATTR_MIN_TEMP: 15,
        ATTR_MAX_TEMP: 30,
        ATTR_SUPPORTED_FEATURES: SUPPORT_OPERATION_MODE,
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    })

    events = []
    hass.bus.async_listen(EVENT_COMMAND_RECEIVED, events.append)
    await hass.async_block_till_done()

    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.EXECUTE",
                "payload": {
                    "commands": [{
                        "devices": [
                            {"id": "climate.bla"},
                        ],
                        "execution": [{
                            "command": "action.devices.commands."
                                       "ThermostatTemperatureSetpoint",
                            "params": {
                                "thermostatTemperatureSetpoint": 10
                            }
                        }]
                    }]
                }
            }]
        })

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [{
                "ids": ['climate.bla'],
                "status": "ERROR",
                "errorCode": "valueOutOfRange"
            }]
        }
    }

    assert len(events) == 1
    assert events[0].event_type == EVENT_COMMAND_RECEIVED
    assert events[0].data == {
        'request_id': REQ_ID,
        'entity_id': 'climate.bla',
        'execution': {
            'command': 'action.devices.commands.ThermostatTemperatureSetpoint',
            'params': {
                'thermostatTemperatureSetpoint': 10
            }
        }
    }


async def test_serialize_input_boolean(hass):
    """Test serializing an input boolean entity."""
    state = State('input_boolean.bla', 'on')
    # pylint: disable=protected-access
    entity = sh._GoogleEntity(hass, BASIC_CONFIG, state)
    result = await entity.sync_serialize()
    assert result == {
        'id': 'input_boolean.bla',
        'attributes': {},
        'name': {'name': 'bla'},
        'traits': ['action.devices.traits.OnOff'],
        'type': 'action.devices.types.SWITCH',
        'willReportState': False,
    }


async def test_unavailable_state_doesnt_sync(hass):
    """Test that an unavailable entity does not sync over."""
    light = DemoLight(
        None, 'Demo Light',
        state=False,
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    light._available = False    # pylint: disable=protected-access
    await light.async_update_ha_state()

    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.SYNC"
            }]
        })

    assert result == {
        'requestId': REQ_ID,
        'payload': {
            'agentUserId': 'test-agent',
            'devices': []
        }
    }


async def test_empty_name_doesnt_sync(hass):
    """Test that an entity with empty name does not sync over."""
    light = DemoLight(
        None, ' ',
        state=False,
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    await light.async_update_ha_state()

    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, 'test-agent',
        {
            "requestId": REQ_ID,
            "inputs": [{
                "intent": "action.devices.SYNC"
            }]
        })

    assert result == {
        'requestId': REQ_ID,
        'payload': {
            'agentUserId': 'test-agent',
            'devices': []
        }
    }


async def test_query_disconnect(hass):
    """Test a disconnect message."""
    result = await sh.async_handle_message(
        hass, BASIC_CONFIG, 'test-agent',
        {
            'inputs': [
                {'intent': 'action.devices.DISCONNECT'}
            ],
            'requestId': REQ_ID
        })

    assert result is None


async def test_trait_execute_adding_query_data(hass):
    """Test a trait execute influencing query data."""
    hass.config.api = Mock(base_url='http://1.1.1.1:8123')
    hass.states.async_set('camera.office', 'idle', {
        'supported_features': camera.SUPPORT_STREAM
    })

    with patch('homeassistant.components.camera.async_request_stream',
               return_value=mock_coro('/api/streams/bla')):
        result = await sh.async_handle_message(
            hass, BASIC_CONFIG, None,
            {
                "requestId": REQ_ID,
                "inputs": [{
                    "intent": "action.devices.EXECUTE",
                    "payload": {
                        "commands": [{
                            "devices": [
                                {"id": "camera.office"},
                            ],
                            "execution": [{
                                "command":
                                "action.devices.commands.GetCameraStream",
                                "params": {
                                    "StreamToChromecast": True,
                                    "SupportedStreamProtocols": [
                                        "progressive_mp4",
                                        "hls",
                                        "dash",
                                        "smooth_stream"
                                    ]
                                }
                            }]
                        }]
                    }
                }]
            })

    assert result == {
        "requestId": REQ_ID,
        "payload": {
            "commands": [{
                "ids": ['camera.office'],
                "status": "SUCCESS",
                "states": {
                    "online": True,
                    'cameraStreamAccessUrl':
                    'http://1.1.1.1:8123/api/streams/bla',
                }
            }]
        }
    }
