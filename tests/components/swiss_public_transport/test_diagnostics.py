"""Tests for the diagnostics data provided by the Swiss public transport integration."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.swiss_public_transport.const import DEFAULT_UPDATE_TIME
from homeassistant.components.swiss_public_transport.helper import Stats
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_config_entries import FrozenDateTimeFactory
from tests.typing import ClientSessionGenerator

FIXED_DATE = datetime(2025, 1, 9, 0, 0, 0)


@pytest.mark.parametrize(
    ("previous_stats", "raise_error"),
    [
        ({}, None),
        (
            {
                "2025-01-01": Stats(count=0, errors=0),
                "2025-01-02": Stats(count=0, errors=0),
                "2025-01-03": Stats(count=0, errors=0),
            },
            None,
        ),
        ({}, OpendataTransportConnectionError),
        ({}, OpendataTransportError),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_opendata_client: AsyncMock,
    swiss_public_transport_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    previous_stats,
    raise_error: Exception,
) -> None:
    """Test diagnostics."""
    with patch(
        "homeassistant.components.swiss_public_transport.helper.dt_util.now",
        autospec=True,
        return_value=FIXED_DATE,
    ):
        await setup_integration(hass, swiss_public_transport_config_entry)

        assert swiss_public_transport_config_entry.state is ConfigEntryState.LOADED

        swiss_public_transport_config_entry.runtime_data.stats = previous_stats

        mock_opendata_client.async_get_data.side_effect = raise_error

        freezer.tick(DEFAULT_UPDATE_TIME)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            await get_diagnostics_for_config_entry(
                hass, hass_client, swiss_public_transport_config_entry
            )
        )["stats"] == snapshot
