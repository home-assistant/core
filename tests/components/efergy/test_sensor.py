"""The tests for Efergy sensor platform."""

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

token = "9p6QGJ7dpZfO3fqPTBk1fyEmjV1cGoLT"
multi_sensor_token = "9r6QGF7dpZfO3fqPTBl1fyRmjV1cGoLT"

ONE_SENSOR_CONFIG = {
    "platform": "efergy",
    "app_token": token,
    "utc_offset": "300",
    "monitored_variables": [
        {"type": "amount", "period": "day"},
        {"type": "instant_readings"},
        {"type": "budget"},
        {"type": "cost", "period": "day", "currency": "USD"},
        {"type": "current_values"},
    ],
}

MULTI_SENSOR_CONFIG = {
    "platform": "efergy",
    "app_token": multi_sensor_token,
    "utc_offset": "300",
    "monitored_variables": [{"type": "current_values"}],
}


def mock_responses(aioclient_mock: AiohttpClientMocker):
    """Mock responses for Efergy."""
    base_url = "https://engage.efergy.com/mobile_proxy/"
    aioclient_mock.get(
        f"{base_url}getInstant?token={token}",
        text=load_fixture("efergy/efergy_instant.json"),
    )
    aioclient_mock.get(
        f"{base_url}getEnergy?token={token}&offset=300&period=day",
        text=load_fixture("efergy/efergy_energy.json"),
    )
    aioclient_mock.get(
        f"{base_url}getBudget?token={token}",
        text=load_fixture("efergy/efergy_budget.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCost?token={token}&offset=300&period=day",
        text=load_fixture("efergy/efergy_cost.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCurrentValuesSummary?token={token}",
        text=load_fixture("efergy/efergy_current_values_single.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCurrentValuesSummary?token={multi_sensor_token}",
        text=load_fixture("efergy/efergy_current_values_multi.json"),
    )


async def test_single_sensor_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test for successfully setting up the Efergy platform."""
    mock_responses(aioclient_mock)
    assert await async_setup_component(hass, "sensor", {"sensor": ONE_SENSOR_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_usage")
    assert state.state == "1580"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    state = hass.states.get("sensor.energy_consumed")
    assert state.state == "38.21"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    state = hass.states.get("sensor.energy_budget")
    assert state.state == "ok"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get("sensor.energy_cost")
    assert state.state == "5.27"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "USD"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    state = hass.states.get("sensor.efergy_728386")
    assert state.state == "1628"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT


async def test_multi_sensor_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test for multiple sensors in one household."""
    mock_responses(aioclient_mock)
    assert await async_setup_component(hass, "sensor", {"sensor": MULTI_SENSOR_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.efergy_728386")
    assert state.state == "218"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    state = hass.states.get("sensor.efergy_0")
    assert state.state == "1808"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    state = hass.states.get("sensor.efergy_728387")
    assert state.state == "312"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
