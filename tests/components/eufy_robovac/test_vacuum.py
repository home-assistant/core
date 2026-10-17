"""Tests for the Eufy RoboVac vacuum entity."""

from unittest.mock import AsyncMock

from eufy_robovac import RoboVacActivity, RoboVacConnectionError, RoboVacState
import pytest

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import DEVICE_ID, ENTITY_ID

from tests.common import MockConfigEntry

EXPECTED_FEATURES = (
    VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STATE
)


async def test_entity_state_naming_and_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the primary entity follows naming and device conventions."""
    await init_integration(hass, mock_config_entry, mock_robovac)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == VacuumActivity.IDLE
    assert state.attributes["friendly_name"] == "Hall Vacuum"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == EXPECTED_FEATURES

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == DEVICE_ID
    assert entity.original_name is None

    device = device_registry.async_get_device_by_identifier(
        ("eufy_robovac", DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Eufy"
    assert device.model == "T2253"
    assert device.name == "Hall Vacuum"


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_START, "start"),
        (SERVICE_PAUSE, "pause"),
        (SERVICE_RETURN_TO_BASE, "return_home"),
    ],
)
async def test_commands_refresh_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
    service: str,
    method: str,
) -> None:
    """Test supported commands are sent through the library."""
    await init_integration(hass, mock_config_entry, mock_robovac)
    initial_update_count = mock_robovac.update.await_count

    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    getattr(mock_robovac, method).assert_awaited_once()
    assert mock_robovac.update.await_count == initial_update_count + 1


async def test_coordinator_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
) -> None:
    """Test coordinator updates are reflected by the vacuum entity."""
    await init_integration(hass, mock_config_entry, mock_robovac)

    mock_config_entry.runtime_data.async_set_updated_data(
        RoboVacState(
            activity=RoboVacActivity.RETURNING,
            error=None,
            raw_status="chargego",
            raw_error="0",
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == VacuumActivity.RETURNING


async def test_update_failure_marks_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
) -> None:
    """Test local update failures mark the vacuum unavailable."""
    await init_integration(hass, mock_config_entry, mock_robovac)
    mock_robovac.update.side_effect = RoboVacConnectionError("unreachable")

    await mock_config_entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_command_failure_raises_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robovac: AsyncMock,
) -> None:
    """Test local command failures are exposed as Home Assistant errors."""
    await init_integration(hass, mock_config_entry, mock_robovac)
    mock_robovac.start.side_effect = RoboVacConnectionError("unreachable")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_START,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
