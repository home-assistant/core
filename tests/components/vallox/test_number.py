"""Tests for Vallox number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the number entities."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("metrics", [{"A_CYC_HOME_AIR_TEMP_TARGET": None}])
async def test_number_value_missing(hass: HomeAssistant) -> None:
    """Test a number value the unit does not report."""
    state = hass.states.get("number.vallox_supply_air_temperature_home")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "metric_key"),
    [
        pytest.param(
            "number.vallox_supply_air_temperature_home",
            "A_CYC_HOME_AIR_TEMP_TARGET",
            id="supply_air_temperature_home",
        ),
        pytest.param(
            "number.vallox_supply_air_temperature_away",
            "A_CYC_AWAY_AIR_TEMP_TARGET",
            id="supply_air_temperature_away",
        ),
        pytest.param(
            "number.vallox_supply_air_temperature_boost",
            "A_CYC_BOOST_AIR_TEMP_TARGET",
            id="supply_air_temperature_boost",
        ),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    entity_id: str,
    metric_key: str,
) -> None:
    """Test setting the number entities."""
    value = 22.0

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_vallox_client.set_values.assert_called_once_with({metric_key: value})
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2
