"""Test the Casper Glow select platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from pycasperglow import CasperGlowError, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.casper_glow.const import (
    DIMMING_TIME_OPTIONS,
    SORTED_BRIGHTNESS_LEVELS,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform

ENTITY_ID = "select.jar_dimming_time"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all select entities match the snapshot."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_state_from_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that the select entity shows dimming time reported by device callback."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await fire_callbacks(
        GlowState(configured_dimming_time_minutes=int(DIMMING_TIME_OPTIONS[2]))
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == DIMMING_TIME_OPTIONS[2]


async def test_select_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test selecting a dimming time option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, "option": DIMMING_TIME_OPTIONS[1]},
        blocking=True,
    )

    mock_casper_glow.set_brightness_and_dimming_time.assert_called_once_with(
        SORTED_BRIGHTNESS_LEVELS[0], int(DIMMING_TIME_OPTIONS[1])
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == DIMMING_TIME_OPTIONS[1]

    # A subsequent device callback must not overwrite the user's selection.
    await fire_callbacks(
        GlowState(configured_dimming_time_minutes=int(DIMMING_TIME_OPTIONS[0]))
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == DIMMING_TIME_OPTIONS[1]


async def test_select_option_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that a set_brightness_and_dimming_time error raises HomeAssistantError."""
    mock_casper_glow.set_brightness_and_dimming_time.side_effect = CasperGlowError(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, "option": DIMMING_TIME_OPTIONS[1]},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_select_state_update_via_callback_after_command_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that device callbacks correctly update state even after a command failure."""
    mock_casper_glow.set_brightness_and_dimming_time.side_effect = CasperGlowError(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, "option": DIMMING_TIME_OPTIONS[1]},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Device sends a push state update — entity reflects true state
    await fire_callbacks(
        GlowState(configured_dimming_time_minutes=int(DIMMING_TIME_OPTIONS[1]))
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == DIMMING_TIME_OPTIONS[1]


async def test_select_ignores_remaining_time_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that callbacks with only remaining time do not change the select state."""
    await fire_callbacks(GlowState(dimming_time_remaining_ms=2_640_000))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that the dimming time is restored from the last known state on restart."""
    mock_restore_cache(hass, (State(ENTITY_ID, DIMMING_TIME_OPTIONS[3]),))
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == DIMMING_TIME_OPTIONS[3]

    # Coordinator should be seeded with the restored value.
    assert mock_config_entry.runtime_data.last_dimming_time_minutes == int(
        DIMMING_TIME_OPTIONS[3]
    )


@pytest.mark.parametrize(
    "restored_state",
    [STATE_UNKNOWN, "invalid", "999"],
)
async def test_restore_state_ignores_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    restored_state: str,
) -> None:
    """Test that invalid or unsupported restored states are ignored."""
    mock_restore_cache(hass, (State(ENTITY_ID, restored_state),))
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert mock_config_entry.runtime_data.last_dimming_time_minutes is None
