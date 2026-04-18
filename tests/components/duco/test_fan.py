"""Tests for the Duco fan platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError, DucoError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

_FAN_ENTITY = "fan.living"


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the fan platform for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", [Platform.FAN]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.usefixtures("init_integration")
async def test_fan_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the fan entity is created with the correct state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "service_data", "expected_duco_state"),
    [
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 0}, "AUTO"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 33}, "CNT1"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 66}, "CNT2"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 100}, "CNT3"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "auto"}, "AUTO"),
    ],
)
async def test_fan_set_state(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    service: str,
    service_data: dict,
    expected_duco_state: str,
) -> None:
    """Test that fan service calls map to the correct Duco ventilation state."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _FAN_ENTITY, **service_data},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(
        1, expected_duco_state
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [DucoConnectionError("Connection refused"), DucoError("Unexpected error")],
)
async def test_fan_set_state_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test that a HomeAssistantError is raised on API failure."""
    mock_duco_client.async_set_ventilation_state = AsyncMock(side_effect=exception)

    with pytest.raises(HomeAssistantError, match="Failed to set ventilation state"):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: _FAN_ENTITY, ATTR_PERCENTAGE: 100},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_FAN_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
