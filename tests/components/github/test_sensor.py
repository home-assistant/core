"""Test GitHub sensor."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.github.const import FALLBACK_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_SENSOR_ENTITY = "sensor.octocat_hello_world_latest_release"


async def test_sensor_updates_with_empty_release_array(
    hass: HomeAssistant,
    github_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor updates by default GitHub sensors."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(TEST_SENSOR_ENTITY)
    assert state.state == "v1.0.0"

    github_client.graphql.return_value.data["data"]["repository"]["release"] = None

    freezer.tick(FALLBACK_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    new_state = hass.states.get(TEST_SENSOR_ENTITY)
    assert new_state.state == STATE_UNAVAILABLE
