"""Tests for the Gatus binary sensor platform."""

import json
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import load_fixture, snapshot_platform

TEST_ENTRY_ID = "1234567890abcdef1234567890abcdef"


async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_success.json"
    )
    mock_data = json.loads(fixture_data)

    config_entry = await setup_integration(
        hass, mock_gatus_client, mock_data, entry_id=TEST_ENTRY_ID
    )

    entity_registry = er.async_get(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
