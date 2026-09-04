"""Tests for the weheat diagnostics."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.heat_pump import HeatPump

from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_HP_UUID

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def mock_separate_heat_pumps() -> Generator[None]:
    """Mock the two heat pump instances a config entry really builds.

    Each coordinator builds its own, and the diagnostics read a different one
    for the logs than for the energy, so they have to report different content
    for the test to notice the wrong one being read.
    """
    logs, energy = (MagicMock(spec_set=HeatPump) for _ in range(2))
    logs.raw_content = {"heat_pump_id": TEST_HP_UUID, "t_water_in": 11}
    energy.raw_content = {"heat_pump_id": TEST_HP_UUID, "total_ein_heating": 12345}

    with patch(
        "homeassistant.components.weheat.coordinator.HeatPump",
        side_effect=[logs, energy],
    ):
        yield


@pytest.mark.usefixtures("mock_weheat_discover", "mock_separate_heat_pumps")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_diagnostics_without_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_weheat_heat_pump: AsyncMock,
) -> None:
    """Test that diagnostics are returned when the heat pump reported nothing yet."""
    mock_weheat_heat_pump.raw_content = None

    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["heat_pumps"][0]["logs"] == {}
    assert diagnostics["heat_pumps"][0]["energy"] == {}
