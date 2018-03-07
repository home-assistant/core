"""Test Google Smart Home."""
from homeassistant.setup import async_setup_component
from homeassistant.components.google_assistant import trait, smart_home as sh
from homeassistant.components.light.demo import DemoLight


BASIC_CONFIG = sh.Config(
    should_expose=lambda state: True,
    agent_user_id='test-agent',
)
REQ_ID = 'ff36a3cc-ec34-11e6-b1a0-64510650abcf'


async def test_sync_message(hass):
    """Test a sync message."""
    light = DemoLight(
        None, 'Demo Light',
        state=False,
        rgb=[237, 224, 33]
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    await light.async_update_ha_state()

    result = await sh.async_handle_message(hass, BASIC_CONFIG, {
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
                    'temperatureMinK': 6493,
                    'temperatureMaxK': 2000,
                }
            }]
        }
    }


async def test_query_message(hass):
    """Test a sync message."""
    light = DemoLight(
        None, 'Demo Light',
        state=False,
        rgb=[237, 224, 33]
    )
    light.hass = hass
    light.entity_id = 'light.demo_light'
    await light.async_update_ha_state()

    light2 = DemoLight(
        None, 'Another Light',
        state=True,
        rgb=[237, 224, 33],
        ct=400,
        brightness=78,
    )
    light2.hass = hass
    light2.entity_id = 'light.another_light'
    await light2.async_update_ha_state()

    result = await sh.async_handle_message(hass, BASIC_CONFIG, {
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
                        'spectrumRGB': 15589409,
                        'temperature': 2500,
                    }
                },
            }
        }
    }


async def test_execute(hass):
    """Test an execute command."""
    await async_setup_component(hass, 'light', {
        'light': {'platform': 'demo'}
    })

    result = await sh.async_handle_message(hass, BASIC_CONFIG, {
        "requestId": REQ_ID,
        "inputs": [{
            "intent": "action.devices.EXECUTE",
            "payload": {
                "commands": [{
                    "devices": [
                        {"id": "light.non_existing"},
                        {"id": "light.bed_light"},
                    ],
                    "execution": [{
                        "command": "action.devices.commands.OnOff",
                        "params": {
                            "on": True
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
                "ids": ['light.bed_light'],
                "status": "SUCCESS",
                "states": {
                    "on": True,
                    "online": True,
                    'brightness': 70,
                    'color': {
                        'spectrumRGB': 16110848,
                        'temperature': 2631,
                    },
                }
            }]
        }
    }
