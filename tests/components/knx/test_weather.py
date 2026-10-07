"""Test KNX weather."""

import pytest

from homeassistant.components.knx.schema import WeatherSchema
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from . import KnxEntityGenerator
from .conftest import KNXTestKit


async def test_weather(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX weather."""

    await knx.setup_integration(
        {
            WeatherSchema.PLATFORM: {
                CONF_NAME: "test",
                WeatherSchema.CONF_KNX_WIND_ALARM_ADDRESS: "1/1/1",
                WeatherSchema.CONF_KNX_RAIN_ALARM_ADDRESS: "1/1/2",
                WeatherSchema.CONF_KNX_FROST_ALARM_ADDRESS: "1/1/3",
                WeatherSchema.CONF_KNX_HUMIDITY_ADDRESS: "1/1/4",
                WeatherSchema.CONF_KNX_BRIGHTNESS_EAST_ADDRESS: "1/1/5",
                WeatherSchema.CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS: "1/1/6",
                WeatherSchema.CONF_KNX_BRIGHTNESS_WEST_ADDRESS: "1/1/7",
                WeatherSchema.CONF_KNX_BRIGHTNESS_NORTH_ADDRESS: "1/1/8",
                WeatherSchema.CONF_KNX_WIND_SPEED_ADDRESS: "1/1/9",
                WeatherSchema.CONF_KNX_WIND_BEARING_ADDRESS: "1/1/10",
                WeatherSchema.CONF_KNX_TEMPERATURE_ADDRESS: "1/1/11",
                WeatherSchema.CONF_KNX_DAY_NIGHT_ADDRESS: "1/1/12",
                WeatherSchema.CONF_KNX_AIR_PRESSURE_ADDRESS: "1/1/13",
            }
        }
    )
    state = hass.states.get("weather.test")
    assert state.state is ATTR_CONDITION_EXCEPTIONAL

    # StateUpdater initialize states
    await knx.assert_read("1/1/11")
    await knx.receive_response("1/1/11", (0, 40))

    # brightness
    await knx.assert_read("1/1/6")
    await knx.assert_read("1/1/8")
    await knx.receive_response("1/1/6", (0x7C, 0x5E))
    await knx.receive_response("1/1/8", (0x7C, 0x5E))
    await knx.assert_read("1/1/5")
    await knx.assert_read("1/1/7")
    await knx.receive_response("1/1/7", (0x7C, 0x5E))
    await knx.receive_response("1/1/5", (0x7C, 0x5E))

    # wind speed
    await knx.assert_read("1/1/9")
    await knx.receive_response("1/1/9", (0, 40))

    # wind bearing
    await knx.assert_read("1/1/10")
    await knx.receive_response("1/1/10", (0xBF,))

    # alarms
    await knx.assert_read("1/1/2")
    await knx.receive_response("1/1/2", False)
    await knx.assert_read("1/1/1")
    await knx.assert_read("1/1/3")
    await knx.receive_response("1/1/1", False)
    await knx.receive_response("1/1/3", False)

    # day night
    await knx.assert_read("1/1/12")
    await knx.receive_response("1/1/12", False)

    # air pressure
    await knx.assert_read("1/1/13")
    await knx.receive_response("1/1/13", (0x6C, 0xAD))

    # humidity
    await knx.assert_read("1/1/4")
    await knx.receive_response("1/1/4", (0, 40))

    # verify state
    state = hass.states.get("weather.test")
    assert state.attributes["temperature"] == 0.4
    assert state.attributes["wind_bearing"] == 270
    assert state.attributes["wind_speed"] == 1.44
    assert state.attributes["pressure"] == 980.58
    assert state.state is ATTR_CONDITION_SUNNY

    # update from KNX - set rain alarm
    await knx.receive_write("1/1/2", True)
    state = hass.states.get("weather.test")
    assert state.state is ATTR_CONDITION_RAINY

    # update from KNX - set wind alarm
    await knx.receive_write("1/1/2", False)
    await knx.receive_write("1/1/1", True)
    state = hass.states.get("weather.test")
    assert state.state is ATTR_CONDITION_WINDY


async def test_weather_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a weather station from UI."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.WEATHER,
        entity_data={"name": "test"},
        knx_data={
            "ga_temperature": {"state": "1/1/11"},
            "ga_rain_alarm": {"state": "1/1/2"},
            "ga_wind_alarm": {"state": "1/1/1"},
            "sync_state": True,
        },
    )
    state = hass.states.get("weather.test")
    assert state.state is ATTR_CONDITION_EXCEPTIONAL

    await knx.assert_read("1/1/11")
    await knx.receive_response("1/1/11", (0, 40))

    await knx.assert_read("1/1/2")
    await knx.receive_response("1/1/2", True)
    await knx.assert_read("1/1/1")
    await knx.receive_response("1/1/1", False)

    state = hass.states.get("weather.test")
    assert state.attributes["temperature"] == 0.4
    assert state.state is ATTR_CONDITION_RAINY


@pytest.mark.parametrize(
    ("invert_day_night", "day_night_payload"),
    [
        # DPT 1.024: `1` is night - yields a clear-night condition
        pytest.param(False, True, id="dpt_1_024"),
        # inverted: `0` is night
        pytest.param(True, False, id="inverted"),
    ],
)
async def test_weather_ui_invert_day_night(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    invert_day_night: bool,
    day_night_payload: bool,
) -> None:
    """Test UI weather day/night follows DPT 1.024 and can be inverted."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.WEATHER,
        entity_data={"name": "test"},
        knx_data={
            "ga_temperature": {"state": "1/1/11"},
            "ga_day_night": {"state": "1/1/12"},
            "invert_day_night": invert_day_night,
            "sync_state": True,
        },
    )
    await knx.assert_read("1/1/11", response=(0, 40))
    await knx.assert_read("1/1/12", response=day_night_payload)
    knx.assert_state("weather.test", ATTR_CONDITION_CLEAR_NIGHT)


async def test_weather_ui_load(knx: KNXTestKit) -> None:
    """Test loading a weather station from storage."""
    await knx.setup_integration(config_store_fixture="config_store_weather.json")

    await knx.assert_read("1/1/11", response=(0, 40))

    # brightness
    await knx.assert_read("1/1/6")
    await knx.assert_read("1/1/8")
    await knx.receive_response("1/1/6", (0x7C, 0x5E))
    await knx.receive_response("1/1/8", (0x7C, 0x5E))
    await knx.assert_read("1/1/5")
    await knx.assert_read("1/1/7")
    await knx.receive_response("1/1/7", (0x7C, 0x5E))
    await knx.receive_response("1/1/5", (0x7C, 0x5E))

    # wind speed
    await knx.assert_read("1/1/9", response=(0, 40))
    # wind bearing
    await knx.assert_read("1/1/10", response=(0xBF,))

    # alarms
    await knx.assert_read("1/1/2", response=False)
    await knx.assert_read("1/1/1")
    await knx.assert_read("1/1/3")
    await knx.receive_response("1/1/1", False)
    await knx.receive_response("1/1/3", False)

    # day night
    await knx.assert_read("1/1/12", response=False)
    # air pressure
    await knx.assert_read("1/1/13", response=(0x6C, 0xAD))
    # humidity
    await knx.assert_read("1/1/4", response=(0, 40))

    knx.assert_state(
        "weather.test",
        ATTR_CONDITION_SUNNY,
        temperature=0.4,
        wind_bearing=270,
    )
