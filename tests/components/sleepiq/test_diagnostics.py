"""Tests for SleepIQ diagnostics."""

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_platform


@pytest.mark.usefixtures("mock_asyncsleepiq")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics leave out account identifiers."""
    entry = await setup_platform(hass, "sensor")

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
