"""Test Google Smart Home."""
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
from homeassistant.setup import async_setup_component
from homeassistant.components import climate
from homeassistant.components.google_assistant import (
    const, trait, helpers, smart_home as sh)
from homeassistant.components.light.demo import DemoLight


BASIC_CONFIG = helpers.Config(
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

    # This should not show up in the sync request
    hass.states.async_set('sensor.no_match', 'something')

    # Excluded via config
    hass.states.async_set('light.not_expose', 'on')

    config = helpers.Config(
        should_expose=lambda state: state.entity_id != 'light.not_expose',
        agent_user_id='test-agent',
        entity_config={
            'light.demo_light': {
                const.CONF_ROOM_HINT: 'Living Room',
                const.CONF_ALIASES: ['Hello', 'World']
            }
        }
    )

    result = await sh.async_handle_message(hass, config, {
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
                    'temperatureMinK': 6493,
                    'temperatureMaxK': 2000,
                },
                'roomHint': 'Living Room'
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
    await hass.services.async_call(
        'light', 'turn_off', {'entity_id': 'light.ceiling_lights'},
        blocking=True)

    result = await sh.async_handle_message(hass, BASIC_CONFIG, {
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
                        'spectrumRGB': 15589409,
                        'temperature': 2631,
                    },
                }
            }]
        }
    }


async def test_raising_error_trait(hass):
    """Test raising an error while executing a trait command."""
    hass.states.async_set('climate.bla', climate.STATE_HEAT, {
        climate.ATTR_MIN_TEMP: 15,
        climate.ATTR_MAX_TEMP: 30,
        ATTR_SUPPORTED_FEATURES: climate.SUPPORT_OPERATION_MODE,
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    })
    result = await sh.async_handle_message(hass, BASIC_CONFIG, {
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
