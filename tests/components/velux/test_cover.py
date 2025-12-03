"""Tests for the Velux cover platform."""

from unittest.mock import AsyncMock

import pytest
from pyvlx.opening_device import Awning, GarageDoor, Gate, RollerShutter, Window

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
)
from homeassistant.components.velux import DOMAIN
from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import update_callback_entity

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

# Apply setup_integration fixture to all tests in this module
pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.COVER


@pytest.mark.parametrize("mock_pyvlx", ["mock_blind"], indirect=True)
async def test_blind_entity_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate registry metadata."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.usefixtures("mock_cover_type")
@pytest.mark.parametrize(
    "mock_cover_type", [Awning, GarageDoor, Gate, RollerShutter, Window], indirect=True
)
@pytest.mark.parametrize(
    "mock_pyvlx",
    ["mock_cover_type"],
    indirect=True,
)
async def test_cover_entity_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate entity metadata."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_cover_device_association(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the cover entity device association."""

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) >= 1

    for entry in entity_entries:
        assert entry.device_id is not None
        device_entry = device_registry.async_get(entry.device_id)
        assert device_entry is not None
        assert (DOMAIN, entry.unique_id) in device_entry.identifiers
        assert device_entry.via_device_id is not None
        via_device_entry = device_registry.async_get(device_entry.via_device_id)
        assert via_device_entry is not None
        assert (
            DOMAIN,
            f"gateway_{mock_config_entry.entry_id}",
        ) in via_device_entry.identifiers


async def test_cover_closed(
    hass: HomeAssistant,
    mock_window: AsyncMock,
) -> None:
    """Test the cover closed state."""

    test_entity_id = "cover.test_window"

    # Initial state should be open
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OPEN

    # Update mock window position to closed percentage
    mock_window.position.position_percent = 100
    # Also directly set position to closed, so this test should
    # continue to be green after the lib is fixed
    mock_window.position.closed = True

    # Trigger entity state update via registered callback
    await update_callback_entity(hass, mock_window)

    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED


# Window command tests


async def test_window_open_close_stop_services(
    hass: HomeAssistant, mock_window: AsyncMock
) -> None:
    """Verify open/close/stop services map to device calls with no wait."""

    entity_id = "cover.test_window"

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
    )
    mock_window.open.assert_awaited_once_with(wait_for_completion=False)

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {"entity_id": entity_id}, blocking=True
    )
    mock_window.close.assert_awaited_once_with(wait_for_completion=False)

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_STOP_COVER, {"entity_id": entity_id}, blocking=True
    )
    mock_window.stop.assert_awaited_once_with(wait_for_completion=False)


async def test_window_set_cover_position_inversion(
    hass: HomeAssistant, mock_window: AsyncMock
) -> None:
    """HA position is inverted for device's Position."""

    entity_id = "cover.test_window"

    # Call with position 30 (=70% for device)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {"entity_id": entity_id, ATTR_POSITION: 30},
        blocking=True,
    )

    # Expect device Position 70%
    args, kwargs = mock_window.set_position.await_args
    position_obj = args[0]
    assert position_obj.position_percent == 70
    assert kwargs.get("wait_for_completion") is False


async def test_window_current_position_and_opening_closing_states(
    hass: HomeAssistant, mock_window: AsyncMock
) -> None:
    """Validate current_position and opening/closing state transitions."""

    entity_id = "cover.test_window"

    # device position 30 -> current_position 70
    mock_window.position.position_percent = 30
    await update_callback_entity(hass, mock_window)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("current_position") == 70
    assert state.state == STATE_OPEN

    # Opening
    mock_window.is_opening = True
    mock_window.is_closing = False
    await update_callback_entity(hass, mock_window)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OPENING

    # Closing
    mock_window.is_opening = False
    mock_window.is_closing = True
    await update_callback_entity(hass, mock_window)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_CLOSING


# Blind command tests


async def test_blind_open_close_stop_tilt_services(
    hass: HomeAssistant, mock_blind: AsyncMock
) -> None:
    """Verify tilt services map to orientation calls."""

    entity_id = "cover.test_blind"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_blind.open_orientation.assert_awaited_once_with(wait_for_completion=False)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_blind.close_orientation.assert_awaited_once_with(wait_for_completion=False)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_blind.stop_orientation.assert_awaited_once_with(wait_for_completion=False)


async def test_blind_set_cover_tilt_position_inversion(
    hass: HomeAssistant, mock_blind: AsyncMock
) -> None:
    """HA tilt position is inverted for device orientation."""

    entity_id = "cover.test_blind"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {"entity_id": entity_id, ATTR_TILT_POSITION: 25},
        blocking=True,
    )

    call = mock_blind.set_orientation.await_args
    orientation_obj = call.kwargs.get("orientation")
    assert orientation_obj is not None
    assert orientation_obj.position_percent == 75
    assert call.kwargs.get("wait_for_completion") is False


async def test_blind_current_tilt_position(
    hass: HomeAssistant, mock_blind: AsyncMock
) -> None:
    """Validate current_tilt_position attribute reflects inverted orientation."""

    entity_id = "cover.test_blind"
    mock_blind.orientation.position_percent = 10
    await update_callback_entity(hass, mock_blind)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("current_tilt_position") == 90


async def test_non_blind_has_no_tilt_position(
    hass: HomeAssistant, mock_window: AsyncMock
) -> None:
    """Non-blind covers should not expose current_tilt_position attribute."""

    entity_id = "cover.test_window"
    await update_callback_entity(hass, mock_window)
    state = hass.states.get(entity_id)
    assert state is not None
    assert "current_tilt_position" not in state.attributes
