"""Tests for SleepIQ diagnostics."""

from unittest.mock import MagicMock

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


@pytest.mark.usefixtures("mock_asyncsleepiq")
async def test_diagnostics_without_sleep_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bed: MagicMock,
) -> None:
    """Test diagnostics still download when a sleeper has no sleep data."""
    mock_bed.sleepers[0].sleep_data = None
    entry = await setup_platform(hass, "sensor")

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    sleepers = diagnostics["beds"][0]["sleepers"]
    assert sleepers[0]["sleep_data"] is None
    assert sleepers[1]["sleep_data"]["sleep_score"] == 78
