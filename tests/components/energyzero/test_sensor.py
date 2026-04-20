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

pytestmark = [pytest.mark.freeze_time("2026-04-10 20:32:59")]


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
@pytest.mark.parametrize("service", ["get_gas_prices", "get_electricity_prices"])
async def test_no_data(
    hass: HomeAssistant,
    mock_energyzero: MagicMock,
    freezer: FrozenDateTimeFactory,
    service: str,
) -> None:
    """Test the EnergyZero - No data available scenarios."""
    if service == "get_electricity_prices":
        # First call (today) succeeds, second call (tomorrow) fails
        mock_energyzero.get_electricity_prices.side_effect = [
            mock_energyzero.get_electricity_prices.return_value,
            EnergyZeroNoDataError,
        ]
        expected_state = str(mock_energyzero.get_gas_prices.return_value.current_price)
    else:
        getattr(mock_energyzero, service).side_effect = EnergyZeroNoDataError
        expected_state = STATE_UNKNOWN

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == expected_state
