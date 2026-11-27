"""Tests for Vallox number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from vallox_websocket_api import Profile

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.const import STATE_UNKNOWN, Platform, TargetKey
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
    ("entity_id", "value", "setter", "profile"),
    [
        pytest.param(
            "number.vallox_supply_air_temperature_home",
            22.0,
            "set_temperature",
            Profile.HOME,
            id="supply_air_temperature_home",
        ),
        pytest.param(
            "number.vallox_supply_air_temperature_away",
            22.0,
            "set_temperature",
            Profile.AWAY,
            id="supply_air_temperature_away",
        ),
        pytest.param(
            "number.vallox_supply_air_temperature_boost",
            22.0,
            "set_temperature",
            Profile.BOOST,
            id="supply_air_temperature_boost",
        ),
        pytest.param(
            "number.vallox_fan_speed_home",
            45,
            "set_fan_speed",
            Profile.HOME,
            id="fan_speed_home",
        ),
        pytest.param(
            "number.vallox_fan_speed_away",
            45,
            "set_fan_speed",
            Profile.AWAY,
            id="fan_speed_away",
        ),
        pytest.param(
            "number.vallox_fan_speed_boost",
            45,
            "set_fan_speed",
            Profile.BOOST,
            id="fan_speed_boost",
        ),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    mock_vallox_client: AsyncMock,
    entity_id: str,
    value: float,
    setter: str,
    profile: Profile,
) -> None:
    """Test setting the number entities."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: entity_id,
            NumberServiceArgument.VALUE: value,
        },
        blocking=True,
    )

    getattr(mock_vallox_client, setter).assert_called_once_with(profile, value)
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2
