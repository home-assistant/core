"""Tests for the diagnostics data provided by the Jewish Calendar integration."""

import datetime as dt

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("location_data"), ["Jerusalem", "New York", None], indirect=True
)
@pytest.mark.parametrize("test_time", [dt.datetime(2025, 5, 19)], indirect=True)
@pytest.mark.usefixtures("setup_at_time")
async def test_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics with different locations."""
    diagnostics_data = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics_data == snapshot
