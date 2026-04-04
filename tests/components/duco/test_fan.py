"""Tests for the Duco fan platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError, DucoError
import pytest

from homeassistant.components.fan import (
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_fan_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the fan entity is created with the correct state."""
    entity_id = "fan.living_ventilation"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON  # fan is always running
    assert state.attributes["preset_mode"] == "auto"

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff_1_ventilation"


@pytest.mark.usefixtures("init_integration")
async def test_fan_turn_on(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
) -> None:
    """Test turning on the fan sets medium (MAN2) by default."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.living_ventilation"},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "MAN2")


@pytest.mark.usefixtures("init_integration")
async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
) -> None:
    """Test turning off the fan returns to AUTO mode."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.living_ventilation"},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "AUTO")


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset_mode", "expected_duco_state"),
    [
        ("high", "MAN3"),
        ("medium_forced", "CNT2"),
        ("away", "EMPT"),
    ],
)
async def test_fan_set_preset_mode(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    preset_mode: str,
    expected_duco_state: str,
) -> None:
    """Test setting a ventilation preset mode maps to the correct Duco state."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "fan.living_ventilation",
            ATTR_PRESET_MODE: preset_mode,
        },
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
async def test_fan_set_preset_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test that a HomeAssistantError is raised on API failure."""
    mock_duco_client.async_set_ventilation_state = AsyncMock(side_effect=exception)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.living_ventilation",
                ATTR_PRESET_MODE: "low",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("fan.living_ventilation")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
