"""Tests for the diagnostics data provided by the EnergyZero integration."""

from unittest.mock import AsyncMock, MagicMock

from energyzero import EnergyZeroNoDataError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.freeze_time("2022-12-07 15:00:00")


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the EnergyZero entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot


async def test_diagnostics_no_gas_today(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_energyzero: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics, no gas sensors available."""
    mock_energyzero.gas_prices.side_effect = EnergyZeroNoDataError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
