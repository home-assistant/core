"""Test GitHub sensor."""
from unittest.mock import patch

from aiogithubapi import GitHubNotModifiedException
import pytest

from homeassistant.components.github.const import DEFAULT_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_SENSOR_ENTITY = "sensor.octocat_hello_world_latest_release"


async def test_sensor_updates_with_not_modified_content(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensor updates by default GitHub sensors."""
    state = hass.states.get(TEST_SENSOR_ENTITY)
    assert state.state == "v1.0.0"
    assert (
        "Content for octocat/Hello-World with RepositoryReleaseDataUpdateCoordinator not modified"
        not in caplog.text
    )

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.list",
        side_effect=GitHubNotModifiedException,
    ):

        async_fire_time_changed(hass, dt.utcnow() + DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert (
            "Content for octocat/Hello-World with RepositoryReleaseDataUpdateCoordinator not modified"
            in caplog.text
        )
    new_state = hass.states.get(TEST_SENSOR_ENTITY)
    assert state.state == new_state.state
