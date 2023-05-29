"""Test GitHub sensor."""
import json

import pytest

from homeassistant.components.github.const import DOMAIN, FALLBACK_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .common import TEST_REPOSITORY

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_SENSOR_ENTITY = "sensor.octocat_hello_world_latest_release"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
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
    headers = json.loads(load_fixture("base_headers.json", DOMAIN))

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"https://api.github.com/repos/{TEST_REPOSITORY}/events",
        json=[],
        headers=headers,
    )
    aioclient_mock.post(
        "https://api.github.com/graphql",
        json=response_json,
        headers=headers,
    )

    async_fire_time_changed(hass, dt.utcnow() + FALLBACK_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    new_state = hass.states.get(TEST_SENSOR_ENTITY)
    assert new_state.state == "unavailable"
