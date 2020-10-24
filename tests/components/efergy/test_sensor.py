"""The tests for Efergy sensor platform."""

from homeassistant.setup import async_setup_component

from tests.common import load_fixture

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
        {"type": "cost", "period": "day", "currency": "$"},
        {"type": "current_values"},
    ],
}

MULTI_SENSOR_CONFIG = {
    "platform": "efergy",
    "app_token": multi_sensor_token,
    "utc_offset": "300",
    "monitored_variables": [{"type": "current_values"}],
}


def mock_responses(mock):
    """Mock responses for Efergy."""
    base_url = "https://engage.efergy.com/mobile_proxy/"
    mock.get(
        f"{base_url}getInstant?token={token}",
        text=load_fixture("efergy_instant.json"),
    )
    mock.get(
        f"{base_url}getEnergy?token={token}&offset=300&period=day",
        text=load_fixture("efergy_energy.json"),
    )
    mock.get(
        f"{base_url}getBudget?token={token}",
        text=load_fixture("efergy_budget.json"),
    )
    mock.get(
        f"{base_url}getCost?token={token}&offset=300&period=day",
        text=load_fixture("efergy_cost.json"),
    )
    mock.get(
        f"{base_url}getCurrentValuesSummary?token={token}",
        text=load_fixture("efergy_current_values_single.json"),
    )
    mock.get(
        f"{base_url}getCurrentValuesSummary?token={multi_sensor_token}",
        text=load_fixture("efergy_current_values_multi.json"),
    )


async def test_single_sensor_readings(hass, requests_mock):
    """Test for successfully setting up the Efergy platform."""
    mock_responses(requests_mock)
    assert await async_setup_component(hass, "sensor", {"sensor": ONE_SENSOR_CONFIG})
    await hass.async_block_till_done()

    assert "38.21" == hass.states.get("sensor.energy_consumed").state
    assert "1580" == hass.states.get("sensor.energy_usage").state
    assert "ok" == hass.states.get("sensor.energy_budget").state
    assert "5.27" == hass.states.get("sensor.energy_cost").state
    assert "1628" == hass.states.get("sensor.efergy_728386").state


async def test_multi_sensor_readings(hass, requests_mock):
    """Test for multiple sensors in one household."""
    mock_responses(requests_mock)
    assert await async_setup_component(hass, "sensor", {"sensor": MULTI_SENSOR_CONFIG})
    await hass.async_block_till_done()

    assert "218" == hass.states.get("sensor.efergy_728386").state
    assert "1808" == hass.states.get("sensor.efergy_0").state
    assert "312" == hass.states.get("sensor.efergy_728387").state
