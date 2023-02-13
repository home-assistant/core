"""Test KNX weather."""
from homeassistant.components.knx.schema import WeatherSchema
from homeassistant.components.weather import (
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

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
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("weather.test")
    assert state.state is ATTR_CONDITION_EXCEPTIONAL

    # StateUpdater initialize states
    await knx.assert_read("1/1/11")
    await knx.receive_response("1/1/11", (0, 40))

    # brightness
    await knx.assert_read("1/1/6")
    await knx.receive_response("1/1/6", (0x7C, 0x5E))
    await knx.assert_read("1/1/8")
    await knx.receive_response("1/1/8", (0x7C, 0x5E))
    await knx.assert_read("1/1/7")
    await knx.receive_response("1/1/7", (0x7C, 0x5E))
    await knx.assert_read("1/1/5")
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
    await knx.assert_read("1/1/3")
    await knx.receive_response("1/1/3", False)
    await knx.assert_read("1/1/1")
    await knx.receive_response("1/1/1", False)

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
