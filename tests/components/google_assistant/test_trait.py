"""Tests for the Google Assistant traits."""
import pytest

from homeassistant.components import (
    climate,
    cover,
    fan,
    input_boolean,
    light,
    lock,
    media_player,
    scene,
    script,
    switch,
    vacuum,
    group,
)
from homeassistant.components.google_assistant import trait, helpers, const
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_SUPPORTED_FEATURES)
from homeassistant.core import State, DOMAIN as HA_DOMAIN
from homeassistant.util import color
from tests.common import async_mock_service

BASIC_CONFIG = helpers.Config(
    should_expose=lambda state: True,
    allow_unlock=False,
    agent_user_id='test-agent',
)

UNSAFE_CONFIG = helpers.Config(
    should_expose=lambda state: True,
    agent_user_id='test-agent',
    allow_unlock=True,
)


async def test_brightness_light(hass):
    """Test brightness trait support for light domain."""
    assert trait.BrightnessTrait.supported(light.DOMAIN,
                                           light.SUPPORT_BRIGHTNESS)

    trt = trait.BrightnessTrait(hass, State('light.bla', light.STATE_ON, {
        light.ATTR_BRIGHTNESS: 243
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'brightness': 95
    }

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_BRIGHTNESS_ABSOLUTE, {
        'brightness': 50
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_BRIGHTNESS_PCT: 50
    }


async def test_brightness_cover(hass):
    """Test brightness trait support for cover domain."""
    assert trait.BrightnessTrait.supported(cover.DOMAIN,
                                           cover.SUPPORT_SET_POSITION)

    trt = trait.BrightnessTrait(hass, State('cover.bla', cover.STATE_OPEN, {
        cover.ATTR_CURRENT_POSITION: 75
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'brightness': 75
    }

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    await trt.execute(trait.COMMAND_BRIGHTNESS_ABSOLUTE, {
        'brightness': 50
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
        cover.ATTR_POSITION: 50
    }


async def test_brightness_media_player(hass):
    """Test brightness trait support for media player domain."""
    assert trait.BrightnessTrait.supported(media_player.DOMAIN,
                                           media_player.SUPPORT_VOLUME_SET)

    trt = trait.BrightnessTrait(hass, State(
        'media_player.bla', media_player.STATE_PLAYING, {
            media_player.ATTR_MEDIA_VOLUME_LEVEL: .3
        }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'brightness': 30
    }

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET)
    await trt.execute(trait.COMMAND_BRIGHTNESS_ABSOLUTE, {
        'brightness': 60
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
        media_player.ATTR_MEDIA_VOLUME_LEVEL: .6
    }


async def test_onoff_group(hass):
    """Test OnOff trait support for group domain."""
    assert trait.OnOffTrait.supported(group.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('group.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('group.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'group.bla',
    }

    off_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'group.bla',
    }


async def test_onoff_input_boolean(hass):
    """Test OnOff trait support for input_boolean domain."""
    assert trait.OnOffTrait.supported(input_boolean.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('input_boolean.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('input_boolean.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, input_boolean.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'input_boolean.bla',
    }

    off_calls = async_mock_service(hass, input_boolean.DOMAIN,
                                   SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'input_boolean.bla',
    }


async def test_onoff_switch(hass):
    """Test OnOff trait support for switch domain."""
    assert trait.OnOffTrait.supported(switch.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('switch.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('switch.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'switch.bla',
    }

    off_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'switch.bla',
    }


async def test_onoff_fan(hass):
    """Test OnOff trait support for fan domain."""
    assert trait.OnOffTrait.supported(fan.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('fan.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('fan.bla', STATE_OFF), BASIC_CONFIG)
    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'fan.bla',
    }

    off_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'fan.bla',
    }


async def test_onoff_light(hass):
    """Test OnOff trait support for light domain."""
    assert trait.OnOffTrait.supported(light.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('light.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('light.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
    }

    off_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
    }


async def test_onoff_cover(hass):
    """Test OnOff trait support for cover domain."""
    assert trait.OnOffTrait.supported(cover.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('cover.bla', cover.STATE_OPEN),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('cover.bla', cover.STATE_CLOSED),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
    }

    off_calls = async_mock_service(hass, cover.DOMAIN,
                                   cover.SERVICE_CLOSE_COVER)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
    }


async def test_onoff_media_player(hass):
    """Test OnOff trait support for media_player domain."""
    assert trait.OnOffTrait.supported(media_player.DOMAIN, 0)

    trt_on = trait.OnOffTrait(hass, State('media_player.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('media_player.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
    }

    off_calls = async_mock_service(hass, media_player.DOMAIN,
                                   SERVICE_TURN_OFF)

    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
    }


async def test_onoff_climate(hass):
    """Test OnOff trait support for climate domain."""
    assert trait.OnOffTrait.supported(climate.DOMAIN, climate.SUPPORT_ON_OFF)

    trt_on = trait.OnOffTrait(hass, State('climate.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('climate.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, climate.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': True
    })
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
    }

    off_calls = async_mock_service(hass, climate.DOMAIN,
                                   SERVICE_TURN_OFF)

    await trt_on.execute(trait.COMMAND_ONOFF, {
        'on': False
    })
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
    }


async def test_dock_vacuum(hass):
    """Test dock trait support for vacuum domain."""
    assert trait.DockTrait.supported(vacuum.DOMAIN, 0)

    trt = trait.DockTrait(hass, State('vacuum.bla', vacuum.STATE_IDLE),
                          BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isDocked': False
    }

    calls = async_mock_service(hass, vacuum.DOMAIN,
                               vacuum.SERVICE_RETURN_TO_BASE)
    await trt.execute(trait.COMMAND_DOCK, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }


async def test_startstop_vacuum(hass):
    """Test startStop trait support for vacuum domain."""
    assert trait.StartStopTrait.supported(vacuum.DOMAIN, 0)

    trt = trait.StartStopTrait(hass, State('vacuum.bla', vacuum.STATE_PAUSED, {
        ATTR_SUPPORTED_FEATURES: vacuum.SUPPORT_PAUSE,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {'pausable': True}

    assert trt.query_attributes() == {
        'isRunning': False,
        'isPaused': True
    }

    start_calls = async_mock_service(hass, vacuum.DOMAIN,
                                     vacuum.SERVICE_START)
    await trt.execute(trait.COMMAND_STARTSTOP, {'start': True})
    assert len(start_calls) == 1
    assert start_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    stop_calls = async_mock_service(hass, vacuum.DOMAIN,
                                    vacuum.SERVICE_STOP)
    await trt.execute(trait.COMMAND_STARTSTOP, {'start': False})
    assert len(stop_calls) == 1
    assert stop_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    pause_calls = async_mock_service(hass, vacuum.DOMAIN,
                                     vacuum.SERVICE_PAUSE)
    await trt.execute(trait.COMMAND_PAUSEUNPAUSE, {'pause': True})
    assert len(pause_calls) == 1
    assert pause_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    unpause_calls = async_mock_service(hass, vacuum.DOMAIN,
                                       vacuum.SERVICE_START)
    await trt.execute(trait.COMMAND_PAUSEUNPAUSE, {'pause': False})
    assert len(unpause_calls) == 1
    assert unpause_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }


async def test_color_spectrum_light(hass):
    """Test ColorSpectrum trait support for light domain."""
    assert not trait.ColorSpectrumTrait.supported(light.DOMAIN, 0)
    assert trait.ColorSpectrumTrait.supported(light.DOMAIN,
                                              light.SUPPORT_COLOR)

    trt = trait.ColorSpectrumTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_HS_COLOR: (0, 94),
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'colorModel': 'rgb'
    }

    assert trt.query_attributes() == {
        'color': {
            'spectrumRGB': 16715535
        }
    }

    assert not trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'temperature': 400
        }
    })
    assert trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'spectrumRGB': 16715792
        }
    })

    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'spectrumRGB': 1052927
        }
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_HS_COLOR: (240, 93.725),
    }


async def test_color_temperature_light(hass):
    """Test ColorTemperature trait support for light domain."""
    assert not trait.ColorTemperatureTrait.supported(light.DOMAIN, 0)
    assert trait.ColorTemperatureTrait.supported(light.DOMAIN,
                                                 light.SUPPORT_COLOR_TEMP)

    trt = trait.ColorTemperatureTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_MIN_MIREDS: 200,
        light.ATTR_COLOR_TEMP: 300,
        light.ATTR_MAX_MIREDS: 500,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'temperatureMinK': 2000,
        'temperatureMaxK': 5000,
    }

    assert trt.query_attributes() == {
        'color': {
            'temperature': 3333
        }
    }

    assert trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'temperature': 400
        }
    })
    assert not trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'spectrumRGB': 16715792
        }
    })

    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, {
            'color': {
                'temperature': 5555
            }
        })
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE

    await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'temperature': 2857
        }
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_COLOR_TEMP: color.color_temperature_kelvin_to_mired(2857)
    }


async def test_color_temperature_light_bad_temp(hass):
    """Test ColorTemperature trait support for light domain."""
    assert not trait.ColorTemperatureTrait.supported(light.DOMAIN, 0)
    assert trait.ColorTemperatureTrait.supported(light.DOMAIN,
                                                 light.SUPPORT_COLOR_TEMP)

    trt = trait.ColorTemperatureTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_MIN_MIREDS: 200,
        light.ATTR_COLOR_TEMP: 0,
        light.ATTR_MAX_MIREDS: 500,
    }), BASIC_CONFIG)

    assert trt.query_attributes() == {
    }


async def test_scene_scene(hass):
    """Test Scene trait support for scene domain."""
    assert trait.SceneTrait.supported(scene.DOMAIN, 0)

    trt = trait.SceneTrait(hass, State('scene.bla', scene.STATE), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, scene.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'scene.bla',
    }


async def test_scene_script(hass):
    """Test Scene trait support for script domain."""
    assert trait.SceneTrait.supported(script.DOMAIN, 0)

    trt = trait.SceneTrait(hass, State('script.bla', STATE_OFF), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, script.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, {})

    # We don't wait till script execution is done.
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'script.bla',
    }


async def test_temperature_setting_climate_range(hass):
    """Test TemperatureSetting trait support for climate domain - range."""
    assert not trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0)
    assert trait.TemperatureSettingTrait.supported(
        climate.DOMAIN, climate.SUPPORT_OPERATION_MODE)

    hass.config.units.temperature_unit = TEMP_FAHRENHEIT

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            climate.ATTR_CURRENT_TEMPERATURE: 70,
            climate.ATTR_CURRENT_HUMIDITY: 25,
            climate.ATTR_OPERATION_MODE: climate.STATE_AUTO,
            climate.ATTR_OPERATION_LIST: [
                climate.STATE_OFF,
                climate.STATE_COOL,
                climate.STATE_HEAT,
                climate.STATE_AUTO,
            ],
            climate.ATTR_TARGET_TEMP_HIGH: 75,
            climate.ATTR_TARGET_TEMP_LOW: 65,
            climate.ATTR_MIN_TEMP: 50,
            climate.ATTR_MAX_TEMP: 80
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,cool,heat,heatcool',
        'thermostatTemperatureUnit': 'F',
    }
    assert trt.query_attributes() == {
        'thermostatMode': 'heatcool',
        'thermostatTemperatureAmbient': 21.1,
        'thermostatHumidityAmbient': 25,
        'thermostatTemperatureSetpointLow': 18.3,
        'thermostatTemperatureSetpointHigh': 23.9,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    await trt.execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, {
        'thermostatTemperatureSetpointHigh': 25,
        'thermostatTemperatureSetpointLow': 20,
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        climate.ATTR_TARGET_TEMP_HIGH: 77,
        climate.ATTR_TARGET_TEMP_LOW: 68,
    }

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_OPERATION_MODE)
    await trt.execute(trait.COMMAND_THERMOSTAT_SET_MODE, {
        'thermostatMode': 'heatcool',
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        climate.ATTR_OPERATION_MODE: climate.STATE_AUTO,
    }

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {
            'thermostatTemperatureSetpoint': -100,
        })
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE
    hass.config.units.temperature_unit = TEMP_CELSIUS


async def test_temperature_setting_climate_setpoint(hass):
    """Test TemperatureSetting trait support for climate domain - setpoint."""
    assert not trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0)
    assert trait.TemperatureSettingTrait.supported(
        climate.DOMAIN, climate.SUPPORT_OPERATION_MODE)

    hass.config.units.temperature_unit = TEMP_CELSIUS

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            climate.ATTR_OPERATION_MODE: climate.STATE_COOL,
            climate.ATTR_OPERATION_LIST: [
                climate.STATE_OFF,
                climate.STATE_COOL,
            ],
            climate.ATTR_MIN_TEMP: 10,
            climate.ATTR_MAX_TEMP: 30,
            climate.ATTR_TEMPERATURE: 18,
            climate.ATTR_CURRENT_TEMPERATURE: 20
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,cool',
        'thermostatTemperatureUnit': 'C',
    }
    assert trt.query_attributes() == {
        'thermostatMode': 'cool',
        'thermostatTemperatureAmbient': 20,
        'thermostatTemperatureSetpoint': 18,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)

    with pytest.raises(helpers.SmartHomeError):
        await trt.execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {
            'thermostatTemperatureSetpoint': -100,
        })

    await trt.execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {
        'thermostatTemperatureSetpoint': 19,
    })
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        climate.ATTR_TEMPERATURE: 19
    }


async def test_lock_unlock_lock(hass):
    """Test LockUnlock trait locking support for lock domain."""
    assert trait.LockUnlockTrait.supported(lock.DOMAIN, lock.SUPPORT_OPEN)

    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_UNLOCKED),
                                BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isLocked': False
    }

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {'lock': True})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)
    await trt.execute(trait.COMMAND_LOCKUNLOCK, {'lock': True})

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'lock.front_door'
    }


async def test_lock_unlock_unlock(hass):
    """Test LockUnlock trait unlocking support for lock domain."""
    assert trait.LockUnlockTrait.supported(lock.DOMAIN, lock.SUPPORT_OPEN)

    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_LOCKED),
                                BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isLocked': True
    }

    assert not trt.can_execute(trait.COMMAND_LOCKUNLOCK, {'lock': False})

    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_LOCKED),
                                UNSAFE_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isLocked': True
    }

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {'lock': False})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_UNLOCK)
    await trt.execute(trait.COMMAND_LOCKUNLOCK, {'lock': False})

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'lock.front_door'
    }


async def test_fan_speed(hass):
    """Test FanSpeed trait speed control support for fan domain."""
    assert trait.FanSpeedTrait.supported(fan.DOMAIN, fan.SUPPORT_SET_SPEED)

    trt = trait.FanSpeedTrait(
        hass, State(
            'fan.living_room_fan', fan.SPEED_HIGH, attributes={
                'speed_list': [
                    fan.SPEED_OFF, fan.SPEED_LOW, fan.SPEED_MEDIUM,
                    fan.SPEED_HIGH
                ],
                'speed': 'low'
            }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'availableFanSpeeds': {
            'ordered': True,
            'speeds': [
                {
                    'speed_name': 'off',
                    'speed_values': [
                        {
                            'speed_synonym': ['stop', 'off'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'low',
                    'speed_values': [
                        {
                            'speed_synonym': [
                                'slow', 'low', 'slowest', 'lowest'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'medium',
                    'speed_values': [
                        {
                            'speed_synonym': ['medium', 'mid', 'middle'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'high',
                    'speed_values': [
                        {
                            'speed_synonym': [
                                'high', 'max', 'fast', 'highest', 'fastest',
                                'maximum'],
                            'lang': 'en'
                        }
                    ]
                }
            ]
        },
        'reversible': False
    }

    assert trt.query_attributes() == {
        'currentFanSpeedSetting': 'low',
        'on': True,
        'online': True
    }

    assert trt.can_execute(
        trait.COMMAND_FANSPEED, params={'fanSpeed': 'medium'})

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_SPEED)
    await trt.execute(trait.COMMAND_FANSPEED, params={'fanSpeed': 'medium'})

    assert len(calls) == 1
    assert calls[0].data == {
        'entity_id': 'fan.living_room_fan',
        'speed': 'medium'
    }


async def test_modes(hass):
    """Test Mode trait."""
    assert trait.ModesTrait.supported(
        media_player.DOMAIN, media_player.SUPPORT_SELECT_SOURCE)

    trt = trait.ModesTrait(
        hass, State(
            'media_player.living_room', media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_INPUT_SOURCE_LIST: [
                    'media', 'game', 'chromecast', 'plex'
                ],
                media_player.ATTR_INPUT_SOURCE: 'game'
            }),
        BASIC_CONFIG)

    attribs = trt.sync_attributes()
    assert attribs == {
        'availableModes': [
            {
                'name': 'input source',
                'name_values': [
                    {
                        'name_synonym': ['input source'],
                        'lang': 'en'
                    }
                ],
                'settings': [
                    {
                        'setting_name': 'media',
                        'setting_values': [
                            {
                                'setting_synonym': ['media', 'media mode'],
                                'lang': 'en'
                            }
                        ]
                    },
                    {
                        'setting_name': 'game',
                        'setting_values': [
                            {
                                'setting_synonym': ['game', 'game mode'],
                                'lang': 'en'
                            }
                        ]
                    },
                    {
                        'setting_name': 'chromecast',
                        'setting_values': [
                            {
                                'setting_synonym': ['chromecast'],
                                'lang': 'en'
                            }
                        ]
                    }
                ],
                'ordered': False
            }
        ]
    }

    assert trt.query_attributes() == {
        'currentModeSettings': {'source': 'game'},
        'on': True,
        'online': True
    }

    assert trt.can_execute(
        trait.COMMAND_MODES, params={
            'updateModeSettings': {
                trt.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE): 'media'
            }})

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOURCE)
    await trt.execute(
        trait.COMMAND_MODES, params={
            'updateModeSettings': {
                trt.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE): 'media'
            }})

    assert len(calls) == 1
    assert calls[0].data == {
        'entity_id': 'media_player.living_room',
        'source': 'media'
    }
