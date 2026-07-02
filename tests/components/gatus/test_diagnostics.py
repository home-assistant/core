"""Tests for the Gatus diagnostics platform."""

import json
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_gatus_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output matches snapshot."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_success.json"
    )
    mock_data = json.loads(fixture_data)

    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
