"""Test the Google Air Quality sensor."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@pytest.mark.parametrize(
    ("mock_api", "config_fixture_name"),
    [
        ("air_quality_data.json", "mock_config_entry"),
        ("air_quality_data_custom_laqi.json", "mock_config_entry_with_custom_laqi"),
    ],
    indirect=("mock_api",),
)
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    request: pytest.FixtureRequest,
    mock_api: AsyncMock,
    snapshot: SnapshotAssertion,
    config_fixture_name: str,
) -> None:
    """Snapshot test of the sensors."""

    mock_config_entry = request.getfixturevalue(config_fixture_name)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.google_air_quality.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
