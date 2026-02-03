"""Test the Google Air Quality sensor."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_api",
    [
        "air_quality_data.json",
        "air_quality_data_custom_laqi.json",
    ],
    indirect=True,
)
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_with_custom_laqi: MockConfigEntry,
    mock_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test of the sensors."""
    mock_config_entry_with_custom_laqi.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_custom_laqi.entry_id)
    assert mock_config_entry_with_custom_laqi.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.google_air_quality.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry_with_custom_laqi.entry_id
        )
