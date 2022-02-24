"""Test GitHub sensor."""
import json

from homeassistant.components.github.const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_SENSOR_ENTITY = "sensor.octocat_hello_world_latest_release"


async def test_sensor_updates_with_empty_release_array(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the sensor updates by default GitHub sensors."""
    state = hass.states.get(TEST_SENSOR_ENTITY)
    assert state.state == "v1.0.0"

    response_json = json.loads(load_fixture("graphql.json", DOMAIN))
    response_json["data"]["repository"]["release"] = None

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://api.github.com/graphql",
        json=response_json,
        headers=json.loads(load_fixture("base_headers.json", DOMAIN)),
    )

    async_fire_time_changed(hass, dt.utcnow() + DEFAULT_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    new_state = hass.states.get(TEST_SENSOR_ENTITY)
    assert new_state.state == "unavailable"
