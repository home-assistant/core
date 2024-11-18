"""Tests for the diagnostics data provided by the easyEnergy integration."""

from unittest.mock import MagicMock

from easyenergy import EasyEnergyNoDataError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_diagnostics_no_gas_today(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_easyenergy: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics, no gas sensors available."""
    await async_setup_component(hass, "homeassistant", {})
    mock_easyenergy.gas_prices.side_effect = EasyEnergyNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.easyenergy_today_gas_current_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
