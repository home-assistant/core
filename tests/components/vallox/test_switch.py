"""Tests for Vallox switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

BYPASS_LOCKED_ENTITY_ID = "switch.vallox_bypass_locked"


@pytest.mark.usefixtures("mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the switch entities."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_BYPASS_LOCKED": 1}, STATE_ON, id="on"),
        pytest.param({"A_CYC_BYPASS_LOCKED": 0}, STATE_OFF, id="off"),
        pytest.param({"A_CYC_BYPASS_LOCKED": None}, STATE_UNKNOWN, id="missing"),
    ],
)
async def test_bypass_locked_switch_state(
    hass: HomeAssistant, expected_state: str
) -> None:
    """Test the bypass locked switch state."""
    state = hass.states.get(BYPASS_LOCKED_ENTITY_ID)
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "value"),
    [
        pytest.param(SERVICE_TURN_ON, 1, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, 0, id="turn_off"),
    ],
)
async def test_bypass_locked_switch_set(
    hass: HomeAssistant, mock_vallox_client: AsyncMock, service: str, value: int
) -> None:
    """Test setting the bypass locked switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: BYPASS_LOCKED_ENTITY_ID},
        blocking=True,
    )

    mock_vallox_client.set_values.assert_called_once_with(
        {"A_CYC_BYPASS_LOCKED": value}
    )
    # One fetch at setup, and one refresh after the change.
    assert mock_vallox_client.fetch_metric_data.call_count == 2
