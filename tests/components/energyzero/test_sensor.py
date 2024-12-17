"""Tests for the sensors provided by the EnergyZero integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from energyzero import EnergyZeroNoDataError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

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
async def test_no_gas_today(hass: HomeAssistant, mock_energyzero: MagicMock) -> None:
    """Test the EnergyZero - No gas sensors available."""
    await async_setup_component(hass, "homeassistant", {})

    mock_energyzero.gas_prices.side_effect = EnergyZeroNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.energyzero_today_gas_current_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.energyzero_today_gas_current_hour_price"))
    assert state.state == STATE_UNKNOWN
