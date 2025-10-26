"""Tests for the sensors provided by the EnergyZero integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from energyzero import EnergyZeroNoDataError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = [pytest.mark.freeze_time("2022-12-07 15:00:00")]


async def test_sensor(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the EnergyZero - Energy sensors."""
    with patch("homeassistant.components.energyzero.PLATFORMS", ["sensor"]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_no_gas_today(
    hass: HomeAssistant,
    mock_energyzero: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the EnergyZero - No gas sensors available."""
    mock_energyzero.gas_prices.side_effect = EnergyZeroNoDataError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == STATE_UNKNOWN
