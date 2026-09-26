"""Tests for the Rain Bird diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import mock_response
from .test_calendar import SCHEDULE_RESPONSES

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMockResponse
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("platforms", "schedule_responses"),
    [
        # The calendar entity loads the irrigation schedule.
        pytest.param([Platform.CALENDAR], SCHEDULE_RESPONSES, id="schedule"),
        pytest.param([Platform.SENSOR], [], id="no_schedule"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    responses: list[AiohttpClientMockResponse],
    schedule_responses: list[str],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics include the device state and any loaded schedule."""
    responses.extend(mock_response(response) for response in schedule_responses)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
