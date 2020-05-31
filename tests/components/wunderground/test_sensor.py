"""The tests for the WUnderground platform."""
import aiohttp
from pytest import raises

import homeassistant.components.wunderground.sensor as wunderground
from homeassistant.const import LENGTH_INCHES, STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, load_fixture

VALID_CONFIG_PWS = {
    "platform": "wunderground",
    "api_key": "foo",
    "pws_id": "bar",
    "monitored_conditions": [
        "weather",
        "feelslike_c",
        "alerts",
        "elevation",
        "location",
    ],
}

VALID_CONFIG = {
    "platform": "wunderground",
    "api_key": "foo",
    "lang": "EN",
    "monitored_conditions": [
        "weather",
        "feelslike_c",
        "alerts",
        "elevation",
        "location",
        "weather_1d_metric",
        "precip_1d_in",
    ],
}

INVALID_CONFIG = {
    "platform": "wunderground",
    "api_key": "BOB",
    "pws_id": "bar",
    "lang": "foo",
    "monitored_conditions": ["weather", "feelslike_c", "alerts"],
}

URL = (
    "http://api.wunderground.com/api/foo/alerts/conditions/forecast/lang"
    ":EN/q/32.87336,-117.22743.json"
)
PWS_URL = "http://api.wunderground.com/api/foo/alerts/conditions/lang:EN/q/pws:bar.json"
INVALID_URL = (
    "http://api.wunderground.com/api/BOB/alerts/conditions/lang:foo/q/pws:bar.json"
)


async def test_setup(hass, aioclient_mock):
    """Test that the component is loaded."""
    aioclient_mock.get(URL, text=load_fixture("wunderground-valid.json"))

    with assert_setup_component(1, "sensor"):
        await async_setup_component(hass, "sensor", {"sensor": VALID_CONFIG})


async def test_setup_pws(hass, aioclient_mock):
    """Test that the component is loaded with PWS id."""
    aioclient_mock.get(PWS_URL, text=load_fixture("wunderground-valid.json"))

    with assert_setup_component(1, "sensor"):
        await async_setup_component(hass, "sensor", {"sensor": VALID_CONFIG_PWS})


async def test_setup_invalid(hass, aioclient_mock):
    """Test that the component is not loaded with invalid config."""
    aioclient_mock.get(INVALID_URL, text=load_fixture("wunderground-error.json"))

    with assert_setup_component(0, "sensor"):
        await async_setup_component(hass, "sensor", {"sensor": INVALID_CONFIG})


async def test_sensor(hass, aioclient_mock):
    """Test the WUnderground sensor class and methods."""
    aioclient_mock.get(URL, text=load_fixture("wunderground-valid.json"))

    await async_setup_component(hass, "sensor", {"sensor": VALID_CONFIG})

    state = hass.states.get("sensor.pws_weather")
    assert state.state == "Clear"
    assert state.name == "Weather Summary"
    assert "unit_of_measurement" not in state.attributes
    assert (
        state.attributes["entity_picture"] == "https://icons.wxug.com/i/c/k/clear.gif"
    )

    state = hass.states.get("sensor.pws_alerts")
    assert state.state == "1"
    assert state.name == "Alerts"
    assert state.attributes["Message"] == "This is a test alert message"
    assert state.attributes["icon"] == "mdi:alert-circle-outline"
    assert "entity_picture" not in state.attributes

    state = hass.states.get("sensor.pws_location")
    assert state.state == "Holly Springs, NC"
    assert state.name == "Location"

    state = hass.states.get("sensor.pws_elevation")
    assert state.state == "413"
    assert state.name == "Elevation"

    state = hass.states.get("sensor.pws_feelslike_c")
    assert state.state == "40"
    assert state.name == "Feels Like"
    assert "entity_picture" not in state.attributes
    assert state.attributes["unit_of_measurement"] == TEMP_CELSIUS

    state = hass.states.get("sensor.pws_weather_1d_metric")
    assert state.state == "Mostly Cloudy. Fog overnight."
    assert state.name == "Tuesday"

    state = hass.states.get("sensor.pws_precip_1d_in")
    assert state.state == "0.03"
    assert state.name == "Precipitation Intensity Today"
    assert state.attributes["unit_of_measurement"] == LENGTH_INCHES


async def test_connect_failed(hass, aioclient_mock):
    """Test the WUnderground connection error."""
    aioclient_mock.get(URL, exc=aiohttp.ClientError())
    with raises(PlatformNotReady):
        await wunderground.async_setup_platform(hass, VALID_CONFIG, lambda _: None)


async def test_invalid_data(hass, aioclient_mock):
    """Test the WUnderground invalid data."""
    aioclient_mock.get(URL, text=load_fixture("wunderground-invalid.json"))

    await async_setup_component(hass, "sensor", {"sensor": VALID_CONFIG})

    for condition in VALID_CONFIG["monitored_conditions"]:
        state = hass.states.get(f"sensor.pws_{condition}")
        assert state.state == STATE_UNKNOWN


async def test_entity_id_with_multiple_stations(hass, aioclient_mock):
    """Test not generating duplicate entity ids with multiple stations."""
    aioclient_mock.get(URL, text=load_fixture("wunderground-valid.json"))
    aioclient_mock.get(PWS_URL, text=load_fixture("wunderground-valid.json"))

    config = [VALID_CONFIG, {**VALID_CONFIG_PWS, "entity_namespace": "hi"}]
    await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.pws_weather")
    assert state is not None
    assert state.state == "Clear"

    state = hass.states.get("sensor.hi_pws_weather")
    assert state is not None
    assert state.state == "Clear"


async def test_fails_because_of_unique_id(hass, aioclient_mock):
    """Test same config twice fails because of unique_id."""
    aioclient_mock.get(URL, text=load_fixture("wunderground-valid.json"))
    aioclient_mock.get(PWS_URL, text=load_fixture("wunderground-valid.json"))

    config = [
        VALID_CONFIG,
        {**VALID_CONFIG, "entity_namespace": "hi"},
        VALID_CONFIG_PWS,
    ]
    await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    states = hass.states.async_all()
    expected = len(VALID_CONFIG["monitored_conditions"]) + len(
        VALID_CONFIG_PWS["monitored_conditions"]
    )
    assert len(states) == expected
