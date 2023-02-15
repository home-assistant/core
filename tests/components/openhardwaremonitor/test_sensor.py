"""The tests for the Open Hardware Monitor platform."""
import requests_mock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test for successfully setting up the platform."""
    config = {
        "sensor": {
            "platform": "openhardwaremonitor",
            "host": "localhost",
            "port": 8085,
        }
    }

    requests_mock.get(
        "http://localhost:8085/data.json",
        text=load_fixture("openhardwaremonitor.json"),
    )

    await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entities = hass.states.async_entity_ids("sensor")
    assert len(entities) == 38

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_1")

    assert state is not None
    assert state.state == "31.0"

    state = hass.states.get("sensor.test_pc_intel_core_i7_7700_temperatures_cpu_core_2")

    assert state is not None
    assert state.state == "30.0"
