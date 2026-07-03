"""Test GitHub sensor."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.github.const import FALLBACK_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

TEST_SENSOR_ENTITY = "sensor.octocat_hello_world_latest_release"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    github_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.github.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        (
            "sensor.octocat_hello_world_latest_commit_date",
            "2024-01-02T00:00:00+00:00",
        ),
        (
            "sensor.octocat_hello_world_latest_issue_created",
            "2024-01-01T00:00:00+00:00",
        ),
        (
            "sensor.octocat_hello_world_latest_release_date",
            "2024-01-02T00:00:00+00:00",
        ),
        (
            "sensor.octocat_hello_world_latest_tag_date",
            "2024-01-02T00:00:00+00:00",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "github_client")
async def test_latest_timestamp_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected: str,
) -> None:
    """Test the default-disabled latest_* timestamp sensors."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == expected
    assert state.attributes["device_class"] == "timestamp"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_latest_tag_date_annotated_tag(
    hass: HomeAssistant,
    github_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Annotated tags have a Tag target, so committedDate is absent -> unknown."""
    del github_client.graphql.return_value.data["data"]["repository"]["refs"]["tags"][
        0
    ]["target"]["committed"]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.octocat_hello_world_latest_tag_date")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_latest_release_date_unpublished_release(
    hass: HomeAssistant,
    github_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A release with a null publishedAt (for example a draft) -> unavailable."""
    github_client.graphql.return_value.data["data"]["repository"]["release"][
        "published"
    ] = None
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.octocat_hello_world_latest_release_date")
    assert state.state == STATE_UNAVAILABLE


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
